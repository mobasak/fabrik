#!/usr/bin/env python3
"""
MCP Server for Kilo CLI Integration

Exposes Kilo code review agents as MCP tools for Traycer Epic mode.
This allows Traycer to consult Kilo agents during planning without subprocess access.

Usage:
    Register in MCP config (e.g., ~/.factory/mcp.json):
    {
      "mcpServers": {
        "kilo-code": {
          "command": "python",
          "args": ["/opt/fabrik/scripts/mcp_kilo_server.py"],
          "env": {}
        }
      }
    }

Available tools:
    - kilo_review: Architecture/sequencing review (orchestrator agent)
    - kilo_ask: Verification/Q&A (ask agent)
    - kilo_plan: Planning consultation (plan agent)
    - kilo_general: General analysis (general agent)
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("ERROR: mcp package not installed", file=sys.stderr)
    print("Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Initialize MCP server
mcp = FastMCP("kilo-code")

# Path to Kilo CLI
KILO_CLI = Path("/opt/fabrik/scripts/kilo_code_review.py")
TIMEOUT = 300  # 5 minutes max for Kilo review


async def run_kilo(
    prompt: str,
    agent: str,
    strategy: str = "premium",
    files: list[str] | None = None,
    output_format: str = "json",
) -> dict[str, Any]:
    """
    Run Kilo CLI and return structured result.

    Args:
        prompt: Review/planning prompt
        agent: Kilo agent (ask, orchestrator, plan, general)
        strategy: Tier strategy (free, economy, standard, premium, critical)
        files: List of file paths to attach
        output_format: json or text

    Returns:
        {
            "success": bool,
            "output": str,
            "error": str | None,
            "exit_code": int
        }
    """
    if not KILO_CLI.exists():
        return {
            "success": False,
            "output": "",
            "error": f"Kilo CLI not found at {KILO_CLI}",
            "exit_code": 2,
        }

    # Build command
    cmd = [
        sys.executable,
        str(KILO_CLI),
        "review",
        "--review-agent",
        agent,
        "--strategy",
        strategy,
        "--output",
        output_format,
        "--plan",
        prompt,
    ]

    # Attach files if provided
    if files:
        for file_path in files:
            if Path(file_path).exists():
                cmd.extend(["--file", file_path])

    try:
        # Run Kilo CLI
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=TIMEOUT,
            )
        except TimeoutError:
            process.kill()
            return {
                "success": False,
                "output": "",
                "error": f"Kilo review timed out (>{TIMEOUT}s)",
                "exit_code": 124,
            }

        exit_code = process.returncode or 0
        output_text = stdout.decode() if stdout else ""
        error_text = stderr.decode() if stderr else ""

        # Combine output
        full_output = output_text
        if error_text and exit_code != 0:
            full_output += f"\n\nSTDERR:\n{error_text}"

        return {
            "success": exit_code == 0,
            "output": full_output,
            "error": error_text if exit_code != 0 else None,
            "exit_code": exit_code,
        }

    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": f"{type(e).__name__}: {e}",
            "exit_code": 1,
        }


@mcp.tool()
async def kilo_review(
    prompt: str,
    files: list[str] | None = None,
    strategy: str = "premium",
) -> str:
    """
    Run Kilo architecture/sequencing review using orchestrator agent.

    Use for:
    - Architecture planning
    - Dependency analysis
    - Sequencing validation
    - Structural correctness

    Args:
        prompt: Planning question or review context
        files: List of file paths to attach (optional)
        strategy: Tier strategy (free, economy, standard, premium, critical)

    Returns:
        JSON string with review results or error message

    Example:
        kilo_review(
            prompt="Review WordPress deployment architecture for security gaps",
            files=["/opt/fabrik/specs/sites/ocoron.com.yaml"],
            strategy="premium"
        )
    """
    result = await run_kilo(
        prompt=prompt,
        agent="orchestrator",
        strategy=strategy,
        files=files or [],
        output_format="json",
    )

    if result["success"]:
        return result["output"]
    else:
        return json.dumps(
            {
                "error": result["error"],
                "exit_code": result["exit_code"],
                "tool": "kilo_review",
            },
            indent=2,
        )


@mcp.tool()
async def kilo_ask(
    prompt: str,
    files: list[str] | None = None,
    strategy: str = "standard",
) -> str:
    """
    Run Kilo verification/Q&A using ask agent.

    Use for:
    - Verification passes
    - Clarification questions
    - Sanity checks
    - Follow-up reviews

    Args:
        prompt: Question or verification context
        files: List of file paths to attach (optional)
        strategy: Tier strategy (free, economy, standard, premium, critical)

    Returns:
        JSON string with review results or error message

    Example:
        kilo_ask(
            prompt="Verify fixes applied: WP_ENVIRONMENT_TYPE added, restart policy set",
            files=["/opt/fabrik/specs/sites/ocoron.com.yaml"],
            strategy="standard"
        )
    """
    result = await run_kilo(
        prompt=prompt,
        agent="ask",
        strategy=strategy,
        files=files or [],
        output_format="json",
    )

    if result["success"]:
        return result["output"]
    else:
        return json.dumps(
            {
                "error": result["error"],
                "exit_code": result["exit_code"],
                "tool": "kilo_ask",
            },
            indent=2,
        )


@mcp.tool()
async def kilo_plan(
    prompt: str,
    files: list[str] | None = None,
    strategy: str = "premium",
) -> str:
    """
    Run Kilo planning consultation using plan agent.

    Use for:
    - Strategy planning
    - Approach validation
    - High-level design review
    - Phase sequencing

    Args:
        prompt: Planning question
        files: List of file paths to attach (optional)
        strategy: Tier strategy (free, economy, standard, premium, critical)

    Returns:
        JSON string with review results or error message

    Example:
        kilo_plan(
            prompt="Review phase sequencing for WordPress refactoring",
            files=["/tmp/traycer-epics/epic-123/specs/phase-plan.md"],
            strategy="premium"
        )
    """
    result = await run_kilo(
        prompt=prompt,
        agent="plan",
        strategy=strategy,
        files=files or [],
        output_format="json",
    )

    if result["success"]:
        return result["output"]
    else:
        return json.dumps(
            {
                "error": result["error"],
                "exit_code": result["exit_code"],
                "tool": "kilo_plan",
            },
            indent=2,
        )


@mcp.tool()
async def kilo_general(
    prompt: str,
    files: list[str] | None = None,
    strategy: str = "economy",
) -> str:
    """
    Run Kilo general analysis using general agent.

    Use for:
    - Quick sanity checks
    - General code analysis
    - Low-priority reviews

    Args:
        prompt: Analysis question
        files: List of file paths to attach (optional)
        strategy: Tier strategy (free, economy, standard, premium, critical)

    Returns:
        JSON string with review results or error message

    Example:
        kilo_general(
            prompt="Quick check: does this spec have all required fields?",
            files=["/opt/fabrik/specs/sites/example.com.yaml"],
            strategy="economy"
        )
    """
    result = await run_kilo(
        prompt=prompt,
        agent="general",
        strategy=strategy,
        files=files or [],
        output_format="json",
    )

    if result["success"]:
        return result["output"]
    else:
        return json.dumps(
            {
                "error": result["error"],
                "exit_code": result["exit_code"],
                "tool": "kilo_general",
            },
            indent=2,
        )


if __name__ == "__main__":
    # Run MCP server with stdio transport
    mcp.run(transport="stdio")
