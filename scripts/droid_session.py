#!/usr/bin/env python3
"""
Droid Session Management for Fabrik.

Manages session IDs for droid exec calls to maintain context across related tasks.
Key principle: Same session ID = same context. Model change = context loss.

Usage:
    from scripts.droid_session import get_or_create_session, log_token_usage

    # Get session for a context (e.g., branch name, PR, task)
    session_id = get_or_create_session("feature-auth")

    # After droid exec with -o json, parse and log usage
    log_token_usage(session_id, usage_dict)
"""

import json
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Session cache location
SESSION_CACHE_FILE = Path(__file__).parent / ".droid_sessions.json"
TOKEN_LOG_FILE = Path(__file__).parent / ".droid_token_usage.jsonl"

# Session TTL (sessions older than this are considered stale)
SESSION_TTL_HOURS = 24

# Billing configuration
BILLING_CONFIG = {
    "pro": {
        "tokens_per_month": 20_000_000,
        "price_usd": 20,
        "overage_per_million": 2.70,
    },
    "max": {
        "tokens_per_month": 200_000_000,
        "price_usd": 200,
        "overage_per_million": 2.70,
    },
}

# Current plan (can be updated)
CURRENT_PLAN = "pro"

# Billing cycle day (27th of each month)
BILLING_CYCLE_DAY = 27


def load_sessions() -> dict:
    """Load session cache from disk."""
    if SESSION_CACHE_FILE.exists():
        try:
            return json.loads(SESSION_CACHE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_sessions(sessions: dict) -> None:
    """Save session cache to disk."""
    sessions["_updated"] = datetime.now().isoformat()
    SESSION_CACHE_FILE.write_text(json.dumps(sessions, indent=2))


def get_or_create_session(
    context_key: str,
    model: str | None = None,
    force_new: bool = False,
) -> str:
    """
    Get or create a session ID for a given context.

    CRITICAL: Changing models within a session loses context.
    If model differs from stored session's model, a new session is created.

    Args:
        context_key: Unique key for the context (e.g., branch name, PR ID, task name)
        model: Model being used (if different from stored, new session created)
        force_new: Force creation of a new session

    Returns:
        Session ID (UUID string)
    """
    sessions = load_sessions()

    # Check if we have an existing session for this context
    if not force_new and context_key in sessions:
        session_data = sessions[context_key]

        # Check if session is still valid (not expired)
        created = datetime.fromisoformat(session_data.get("created", "2000-01-01"))
        if datetime.now() - created < timedelta(hours=SESSION_TTL_HOURS):
            # Check if model matches (if specified)
            stored_model = session_data.get("model")
            if model is None or stored_model == model:
                return session_data["session_id"]
            else:
                # Model changed - context will be lost, create new session
                print(
                    f"⚠️  Model changed ({stored_model} → {model}), creating new session (context lost)",
                    file=sys.stderr,
                )

    # Create new session
    session_id = str(uuid.uuid4())
    sessions[context_key] = {
        "session_id": session_id,
        "model": model,
        "created": datetime.now().isoformat(),
        "context_key": context_key,
    }
    save_sessions(sessions)

    return session_id


def invalidate_session(context_key: str) -> bool:
    """
    Invalidate a session (e.g., when task is complete or PR merged).

    Args:
        context_key: The context key to invalidate

    Returns:
        True if session was found and invalidated
    """
    sessions = load_sessions()
    if context_key in sessions:
        del sessions[context_key]
        save_sessions(sessions)
        return True
    return False


def get_session_info(context_key: str) -> dict | None:
    """Get info about a session."""
    sessions = load_sessions()
    return sessions.get(context_key)


def log_token_usage(
    session_id: str,
    usage: dict,
    model: str | None = None,
    context_key: str | None = None,
) -> None:
    """
    Log token usage from a droid exec run.

    Call this after parsing JSON output from `droid exec -o json`.

    Args:
        session_id: The session ID from the response
        usage: The usage dict from JSON response (input_tokens, output_tokens, etc.)
        model: Model used (optional)
        context_key: Context key (optional)
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "model": model,
        "context_key": context_key,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
        "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
        "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
    }

    # Append to JSONL log
    with open(TOKEN_LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def get_token_usage_summary(
    since: datetime | None = None,
    context_key: str | None = None,
) -> dict:
    """
    Get summary of token usage.

    Args:
        since: Only include usage since this time (default: last 24h)
        context_key: Filter by context key (optional)

    Returns:
        Dict with total_input, total_output, total_tokens, by_model breakdown
    """
    if since is None:
        since = datetime.now() - timedelta(hours=24)

    summary = {
        "since": since.isoformat(),
        "total_input": 0,
        "total_output": 0,
        "total_tokens": 0,
        "cache_read_tokens": 0,
        "by_model": {},
        "by_context": {},
        "run_count": 0,
    }

    if not TOKEN_LOG_FILE.exists():
        return summary

    for line in TOKEN_LOG_FILE.read_text().strip().split("\n"):
        if not line:
            continue
        try:
            entry = json.loads(line)
            entry_time = datetime.fromisoformat(entry["timestamp"])

            if entry_time < since:
                continue
            if context_key and entry.get("context_key") != context_key:
                continue

            summary["total_input"] += entry.get("input_tokens", 0)
            summary["total_output"] += entry.get("output_tokens", 0)
            summary["total_tokens"] += entry.get("total_tokens", 0)
            summary["cache_read_tokens"] += entry.get("cache_read_tokens", 0)
            summary["run_count"] += 1

            # By model
            model = entry.get("model", "unknown")
            if model not in summary["by_model"]:
                summary["by_model"][model] = {"input": 0, "output": 0, "runs": 0}
            summary["by_model"][model]["input"] += entry.get("input_tokens", 0)
            summary["by_model"][model]["output"] += entry.get("output_tokens", 0)
            summary["by_model"][model]["runs"] += 1

            # By context
            ctx = entry.get("context_key", "unknown")
            if ctx not in summary["by_context"]:
                summary["by_context"][ctx] = {"input": 0, "output": 0, "runs": 0}
            summary["by_context"][ctx]["input"] += entry.get("input_tokens", 0)
            summary["by_context"][ctx]["output"] += entry.get("output_tokens", 0)
            summary["by_context"][ctx]["runs"] += 1

        except (json.JSONDecodeError, KeyError):
            continue

    return summary


def get_billing_cycle_dates() -> tuple[datetime, datetime]:
    """
    Get the current billing cycle start and end dates.

    Billing cycle runs from the 27th of each month to the 26th of the next month.

    Returns:
        Tuple of (cycle_start, cycle_end) datetime objects
    """
    now = datetime.now()

    if now.day >= BILLING_CYCLE_DAY:
        # We're past the 27th, so cycle started this month
        cycle_start = datetime(now.year, now.month, BILLING_CYCLE_DAY)
        # Cycle ends next month on the 26th
        if now.month == 12:
            cycle_end = datetime(now.year + 1, 1, BILLING_CYCLE_DAY - 1, 23, 59, 59)
        else:
            cycle_end = datetime(now.year, now.month + 1, BILLING_CYCLE_DAY - 1, 23, 59, 59)
    else:
        # We're before the 27th, so cycle started last month
        if now.month == 1:
            cycle_start = datetime(now.year - 1, 12, BILLING_CYCLE_DAY)
        else:
            cycle_start = datetime(now.year, now.month - 1, BILLING_CYCLE_DAY)
        cycle_end = datetime(now.year, now.month, BILLING_CYCLE_DAY - 1, 23, 59, 59)

    return cycle_start, cycle_end


def get_quota_status(current_usage: int | None = None) -> dict:
    """
    Get current quota status including remaining tokens.

    Args:
        current_usage: Current token usage (if known from Factory dashboard).
                      If None, uses local tracking (may be incomplete).

    Returns:
        Dict with quota information
    """
    plan_config = BILLING_CONFIG.get(CURRENT_PLAN, BILLING_CONFIG["pro"])
    monthly_limit = plan_config["tokens_per_month"]

    cycle_start, cycle_end = get_billing_cycle_dates()

    # Get local usage tracking for this cycle
    local_summary = get_token_usage_summary(since=cycle_start)
    local_usage = local_summary["total_tokens"]

    # Use provided usage if available, otherwise use local tracking
    if current_usage is not None:
        usage = current_usage
        usage_source = "factory_dashboard"
    else:
        usage = local_usage
        usage_source = "local_tracking"

    remaining = max(0, monthly_limit - usage)
    usage_percent = (usage / monthly_limit) * 100

    # Calculate days remaining in cycle
    days_remaining = (cycle_end - datetime.now()).days

    # Estimate daily budget
    daily_budget = remaining // max(1, days_remaining) if days_remaining > 0 else 0

    return {
        "plan": CURRENT_PLAN,
        "monthly_limit": monthly_limit,
        "current_usage": usage,
        "usage_source": usage_source,
        "remaining": remaining,
        "usage_percent": round(usage_percent, 1),
        "cycle_start": cycle_start.isoformat(),
        "cycle_end": cycle_end.isoformat(),
        "days_remaining": days_remaining,
        "daily_budget": daily_budget,
        "local_tracked_usage": local_usage,
        "overage_rate": plan_config["overage_per_million"],
    }


def estimate_run_cost(model: str, estimated_tokens: int) -> dict:
    """
    Estimate cost of a droid exec run based on model multiplier.

    Args:
        model: Model ID
        estimated_tokens: Estimated total tokens (input + output)

    Returns:
        Dict with standard_tokens, multiplier, and budget impact
    """
    from scripts.droid_model_updater import get_model_price

    multiplier = get_model_price(model) or 1.0
    standard_tokens = int(estimated_tokens * multiplier)

    status = get_quota_status()
    budget_percent = (
        (standard_tokens / status["remaining"]) * 100 if status["remaining"] > 0 else 100
    )

    return {
        "model": model,
        "multiplier": multiplier,
        "raw_tokens": estimated_tokens,
        "standard_tokens": standard_tokens,
        "remaining_after": status["remaining"] - standard_tokens,
        "budget_percent": round(budget_percent, 2),
        "warning": budget_percent > 10,  # Warn if >10% of remaining budget
    }


def check_quota_warning(current_usage: int | None = None) -> str | None:
    """
    Check if quota is running low and return warning message if needed.

    Args:
        current_usage: Current usage from Factory dashboard (optional)

    Returns:
        Warning message if quota is low, None otherwise
    """
    status = get_quota_status(current_usage)

    if status["usage_percent"] >= 90:
        return f"⚠️  CRITICAL: {status['usage_percent']}% quota used. Only {status['remaining']:,} tokens remaining!"
    elif status["usage_percent"] >= 75:
        return f"⚠️  WARNING: {status['usage_percent']}% quota used. {status['remaining']:,} tokens remaining."
    elif status["usage_percent"] >= 50:
        return (
            f"ℹ️  {status['usage_percent']}% quota used. {status['remaining']:,} tokens remaining."
        )

    return None


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Droid Session Management")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # get-session
    get_cmd = subparsers.add_parser("get", help="Get or create session for context")
    get_cmd.add_argument("context", help="Context key (e.g., branch name)")
    get_cmd.add_argument("-m", "--model", help="Model to use")
    get_cmd.add_argument("--new", action="store_true", help="Force new session")

    # invalidate
    inv_cmd = subparsers.add_parser("invalidate", help="Invalidate a session")
    inv_cmd.add_argument("context", help="Context key to invalidate")

    # usage
    usage_cmd = subparsers.add_parser("usage", help="Show token usage summary")
    usage_cmd.add_argument("--hours", type=int, default=24, help="Hours to look back")
    usage_cmd.add_argument("--context", help="Filter by context")

    # list
    list_cmd = subparsers.add_parser("list", help="List active sessions")

    # quota
    quota_cmd = subparsers.add_parser("quota", help="Show quota status")
    quota_cmd.add_argument("--usage", type=int, help="Current usage from Factory dashboard")

    args = parser.parse_args()

    if args.command == "get":
        session_id = get_or_create_session(args.context, args.model, args.new)
        print(session_id)

    elif args.command == "invalidate":
        if invalidate_session(args.context):
            print(f"Session '{args.context}' invalidated")
        else:
            print(f"No session found for '{args.context}'")

    elif args.command == "usage":
        since = datetime.now() - timedelta(hours=args.hours)
        summary = get_token_usage_summary(since, args.context)
        print(json.dumps(summary, indent=2))

    elif args.command == "list":
        sessions = load_sessions()
        for key, data in sessions.items():
            if key.startswith("_"):
                continue
            print(f"{key}: {data.get('session_id', 'N/A')} (model: {data.get('model', 'N/A')})")

    elif args.command == "quota":
        status = get_quota_status(args.usage)
        print(f"Plan: {status['plan'].upper()} (${BILLING_CONFIG[status['plan']]['price_usd']}/mo)")
        print(f"Cycle: {status['cycle_start'][:10]} to {status['cycle_end'][:10]}")
        print(
            f"Usage: {status['current_usage']:,} / {status['monthly_limit']:,} ({status['usage_percent']}%)"
        )
        print(f"Remaining: {status['remaining']:,} tokens")
        print(f"Days left: {status['days_remaining']}")
        print(f"Daily budget: {status['daily_budget']:,} tokens/day")
        warning = check_quota_warning(args.usage)
        if warning:
            print(f"\n{warning}")

    else:
        parser.print_help()
