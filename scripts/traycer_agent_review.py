#!/usr/bin/env python3
"""
Traycer Agent Auto-Review Wrapper

This script implements the 4-step review workflow for Traycer CLI agents:
1. Self-Review (Step 2.5) - Agent reports on its own work
2. Pre-Kilo (Step 3) - Run final_gate.py
3. Kilo Review (Step 4) - Spawn separate Kilo agent to review
4. Post-Kilo (Step 5) - Run final_gate.py again

Usage (from Traycer CLI agent):
    python /opt/fabrik/scripts/traycer_agent_review.py \
        --task "Task description" \
        --files file1.py file2.py \
        --self-review "Self-review findings" \
        --session-id "ses_xyz" \
        --output json

Exit codes:
    0 - Review passed (all gates PASS, Kilo verdict PASS)
    1 - Review failed (issues found or gates failed)
    2 - Error (script error, invalid input)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.kilo_code_review import KiloReviewConfig, review_loop


def run_final_gate() -> dict[str, Any]:
    """
    Run final_gate.py and return structured result.

    Returns:
        {
            "passed": bool,
            "total_checks": int,
            "failed_checks": int,
            "output": str
        }
    """
    gate_script = Path(__file__).parent / "final_gate.py"

    if not gate_script.exists():
        return {
            "passed": False,
            "total_checks": 0,
            "failed_checks": 1,
            "output": "ERROR: scripts/final_gate.py not found",
        }

    try:
        result = subprocess.run(
            ["python", str(gate_script)],
            capture_output=True,
            text=True,
            timeout=120,
        )

        output = result.stdout + result.stderr

        # Parse output for pass/fail counts
        passed = result.returncode == 0
        total_checks = 0
        failed_checks = 0

        # Extract counts from output (format: "Passed: X" and "Failed: Y")
        for line in output.split("\n"):
            if "Passed:" in line:
                try:
                    total_checks = int(line.split("Passed:")[1].strip().split()[0])
                except (IndexError, ValueError):
                    pass
            if "Failed:" in line:
                try:
                    failed_checks = int(line.split("Failed:")[1].strip().split()[0])
                except (IndexError, ValueError):
                    pass

        return {
            "passed": passed,
            "total_checks": total_checks,
            "failed_checks": failed_checks,
            "output": output,
        }

    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "total_checks": 0,
            "failed_checks": 1,
            "output": "ERROR: final_gate.py timed out (>120s)",
        }
    except Exception as e:
        return {
            "passed": False,
            "total_checks": 0,
            "failed_checks": 1,
            "output": f"ERROR: {type(e).__name__}: {e}",
        }


async def run_kilo_review(
    task_description: str,
    changed_files: list[Path],
    coder_session_id: str,
) -> dict[str, Any]:
    """
    Run Kilo review with a SEPARATE agent (not the coder agent).

    Args:
        task_description: What the coder agent implemented
        changed_files: List of files changed
        coder_session_id: Session ID of the coder agent (for tracking)

    Returns:
        {
            "verdict": "PASS" | "FAIL",
            "summary": str,
            "issues": list[dict],
            "session_id": str,  # Kilo reviewer's session ID
            "cost": float,
            "input_tokens": int,
            "output_tokens": int
        }
    """
    # Create config for review
    config = KiloReviewConfig(
        traycer_plan=task_description,
        review_agent="ask",  # Use Kilo's default reviewer agent
        session_id=None,  # Let Kilo create new session (separate from coder)
        max_iterations=1,  # Single review pass (agent will fix and re-run if needed)
        review_mode="diff_only",  # Review only diff
        output_format="json",
    )

    review_result = await review_loop(files=changed_files, config=config)

    return {
        "verdict": review_result.verdict,
        "summary": review_result.summary,
        "issues": review_result.remaining_issues,
        "session_id": review_result.session_id or "unknown",
        "cost": review_result.usage.get("cost_usd", 0.0),
        "input_tokens": review_result.usage.get("input_tokens", 0),
        "output_tokens": review_result.usage.get("output_tokens", 0),
    }


async def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Traycer Agent Auto-Review Wrapper")
    parser.add_argument(
        "--task",
        required=True,
        help="Task description (what the agent implemented)",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        required=True,
        help="Changed files to review",
    )
    parser.add_argument(
        "--self-review",
        required=True,
        help="Agent's self-review findings (Step 2.5)",
    )
    parser.add_argument(
        "--session-id",
        required=True,
        help="Coder agent's session ID (for tracking)",
    )
    parser.add_argument(
        "--output",
        choices=["json", "text"],
        default="json",
        help="Output format",
    )

    args = parser.parse_args()

    # Parse files
    changed_files = [Path(f) for f in args.files]

    # Validate files exist
    for file in changed_files:
        if not file.exists():
            print(
                json.dumps(
                    {
                        "error": f"File not found: {file}",
                        "exit_code": 2,
                    }
                ),
                file=sys.stderr,
            )
            return 2

    # ========================================================================
    # STEP 2.5: Self-Review (Already done by agent, just record it)

    # Validate self-review is not placeholder or failed
    if "Agent completed implementation" in args.self_review:
        result = {
            "workflow": "traycer_agent_auto_review",
            "error": "Self-review is placeholder. Agent must perform actual self-review.",
            "exit_code": 2,
        }
        if args.output == "json":
            print(json.dumps(result, indent=2))
        else:
            print("❌ ERROR: Self-review is placeholder", file=sys.stderr)
        return 2

    if "SELF-REVIEW FAILED" in args.self_review:
        result = {
            "workflow": "traycer_agent_auto_review",
            "error": "Self-review failed (timeout or error). Cannot proceed.",
            "exit_code": 2,
        }
        if args.output == "json":
            print(json.dumps(result, indent=2))
        else:
            print("❌ ERROR: Self-review failed", file=sys.stderr)
        return 2

    # Validate self-review has required format
    required_markers = [
        "✓ All spec requirements",
        "✓ Edge cases",
        "✓ Env vars",
        "✓ DB changes",
        "⚠ Potential issues",
    ]
    missing = [m for m in required_markers if m not in args.self_review]

    if missing:
        print(f"⚠️  WARNING: Self-review missing sections: {', '.join(missing)}", file=sys.stderr)
        print("⚠️  Proceeding anyway, but self-review may be incomplete", file=sys.stderr)

    # ========================================================================

    self_review = {
        "step": "2.5",
        "name": "Self-Review",
        "findings": args.self_review,
        "status": "COMPLETE",
    }

    # ========================================================================
    # STEP 3: Pre-Kilo Gate
    # ========================================================================

    print("Running Step 3: Pre-Kilo Gate...", file=sys.stderr)
    pre_kilo_result = run_final_gate()

    pre_kilo = {
        "step": "3",
        "name": "Pre-Kilo Gate",
        "passed": pre_kilo_result["passed"],
        "total_checks": pre_kilo_result["total_checks"],
        "failed_checks": pre_kilo_result["failed_checks"],
        "output": pre_kilo_result["output"][:500],  # Truncate
        "status": "PASS" if pre_kilo_result["passed"] else "FAIL",
    }

    if not pre_kilo_result["passed"]:
        # Pre-kilo failed - stop here
        result = {
            "workflow": "traycer_agent_auto_review",
            "coder_session_id": args.session_id,
            "task": args.task,
            "files": [str(f) for f in changed_files],
            "steps": {
                "self_review": self_review,
                "pre_kilo": pre_kilo,
            },
            "final_status": "FAILED_PRE_KILO",
            "exit_code": 1,
        }

        if args.output == "json":
            print(json.dumps(result, indent=2))
        else:
            print(f"❌ Pre-Kilo Gate FAILED ({pre_kilo_result['failed_checks']} checks)")
            print("Fix issues and re-run")

        return 1

    # ========================================================================
    # STEP 4: Kilo Review (Separate Agent)
    # ========================================================================

    print("Running Step 4: Kilo Review (separate agent)...", file=sys.stderr)

    try:
        kilo_result = await run_kilo_review(
            task_description=args.task,
            changed_files=changed_files,
            coder_session_id=args.session_id,
        )

        kilo_review = {
            "step": "4",
            "name": "Kilo Review",
            "reviewer_session_id": kilo_result["session_id"],
            "verdict": kilo_result["verdict"],
            "summary": kilo_result["summary"],
            "issues_count": len(kilo_result["issues"]),
            "issues": kilo_result["issues"][:5],  # First 5 issues
            "cost": kilo_result["cost"],
            "tokens": {
                "input": kilo_result["input_tokens"],
                "output": kilo_result["output_tokens"],
            },
            "status": kilo_result["verdict"],
        }

    except Exception as e:
        kilo_review = {
            "step": "4",
            "name": "Kilo Review",
            "error": f"{type(e).__name__}: {e}",
            "status": "ERROR",
        }

        result = {
            "workflow": "traycer_agent_auto_review",
            "coder_session_id": args.session_id,
            "task": args.task,
            "files": [str(f) for f in changed_files],
            "steps": {
                "self_review": self_review,
                "pre_kilo": pre_kilo,
                "kilo_review": kilo_review,
            },
            "final_status": "ERROR_KILO",
            "exit_code": 2,
        }

        if args.output == "json":
            print(json.dumps(result, indent=2))
        else:
            print(f"⚠️  Kilo Review ERROR: {e}")

        return 2

    # ========================================================================
    # STEP 5: Post-Kilo Gate (Only if Kilo passed)
    # ========================================================================

    post_kilo = None

    if kilo_result["verdict"] == "PASS":
        print("Running Step 5: Post-Kilo Gate...", file=sys.stderr)
        post_kilo_result = run_final_gate()

        post_kilo = {
            "step": "5",
            "name": "Post-Kilo Gate",
            "passed": post_kilo_result["passed"],
            "total_checks": post_kilo_result["total_checks"],
            "failed_checks": post_kilo_result["failed_checks"],
            "output": post_kilo_result["output"][:500],
            "status": "PASS" if post_kilo_result["passed"] else "FAIL",
        }

    # ========================================================================
    # Final Result
    # ========================================================================

    # Determine final status
    if kilo_result["verdict"] == "FAIL":
        final_status = "FAILED_KILO_REVIEW"
        exit_code = 1
    elif post_kilo and not post_kilo["passed"]:
        final_status = "FAILED_POST_KILO"
        exit_code = 1
    else:
        final_status = "PASSED"
        exit_code = 0

    result: dict[str, Any] = {
        "workflow": "traycer_agent_auto_review",
        "coder_session_id": args.session_id,
        "task": args.task,
        "files": [str(f) for f in changed_files],
        "steps": {
            "self_review": self_review,
            "pre_kilo": pre_kilo,
            "kilo_review": kilo_review,
        },
        "final_status": final_status,
        "exit_code": exit_code,
        "next_action": (
            "STOP - Ready for Traycer verification"
            if exit_code == 0
            else "FIX - Review issues and re-run workflow"
        ),
    }

    if post_kilo:
        result["steps"]["post_kilo"] = post_kilo

    # Output
    if args.output == "json":
        print(json.dumps(result, indent=2))
    else:
        print("\n" + "=" * 60)
        print("TRAYCER AGENT AUTO-REVIEW REPORT")
        print("=" * 60)
        print(f"Task: {args.task}")
        print(f"Files: {', '.join(str(f) for f in changed_files)}")
        print()
        print(f"Step 2.5 - Self-Review: {self_review['status']}")
        print(f"Step 3 - Pre-Kilo: {pre_kilo['status']} ({pre_kilo['total_checks']} checks)")
        print(f"Step 4 - Kilo Review: {kilo_review['status']}")
        if kilo_result["verdict"] == "FAIL":
            print(f"  Issues found: {len(kilo_result['issues'])}")
            for issue in kilo_result["issues"][:3]:
                print(
                    f"  - {issue['severity']}: {issue['file']}:{issue['lines']} - {issue['why'][:60]}"
                )
        if post_kilo:
            print(f"Step 5 - Post-Kilo: {post_kilo['status']} ({post_kilo['total_checks']} checks)")
        print()
        print(f"FINAL STATUS: {final_status}")
        print(f"NEXT ACTION: {result['next_action']}")
        print("=" * 60)

    return exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
