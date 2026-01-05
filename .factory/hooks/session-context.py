#!/usr/bin/env python3
"""
Fabrik Session Context Hook - SessionStart

Loads project context when a droid session starts.
Provides droid with relevant project information.

Output goes to stdout and is added to droid context.
"""

import json
import os
import sys
from pathlib import Path


def get_project_info(cwd: str) -> dict:
    """Gather project information from the working directory."""
    info = {
        "project_root": cwd,
        "fabrik_project": False,
        "has_docker": False,
        "has_compose": False,
        "has_env_example": False,
        "has_tests": False,
        "project_type": "unknown",
    }

    cwd_path = Path(cwd)

    # Check for Fabrik markers
    if (cwd_path / "AGENTS.md").exists() or (cwd_path / ".windsurfrules").exists():
        info["fabrik_project"] = True

    # Check for Docker
    if (cwd_path / "Dockerfile").exists():
        info["has_docker"] = True

    if (cwd_path / "compose.yaml").exists() or (cwd_path / "docker-compose.yaml").exists():
        info["has_compose"] = True

    # Check for env example
    if (cwd_path / ".env.example").exists():
        info["has_env_example"] = True

    # Check for tests
    if (cwd_path / "tests").exists() or (cwd_path / "test").exists():
        info["has_tests"] = True

    # Detect project type
    if (cwd_path / "pyproject.toml").exists() or (cwd_path / "requirements.txt").exists():
        info["project_type"] = "python"
    elif (cwd_path / "package.json").exists():
        info["project_type"] = "node"
    elif (cwd_path / "go.mod").exists():
        info["project_type"] = "go"
    elif (cwd_path / "Cargo.toml").exists():
        info["project_type"] = "rust"

    return info


def get_recent_changes(cwd: str) -> list[str]:
    """Get recently modified files."""
    import shutil
    import subprocess

    # Check if git is available
    if not shutil.which("git"):
        return []

    try:
        # First check if we're in a git repo
        check_git = subprocess.run(
            ["git", "rev-parse", "--git-dir"], cwd=cwd, capture_output=True, text=True, timeout=3
        )
        if check_git.returncode != 0:
            return []

        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~5", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return [f for f in result.stdout.strip().split("\n") if f][:10]
    except Exception:
        pass

    return []


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    cwd = input_data.get("cwd", os.getcwd())
    source = input_data.get("source", "startup")

    # Gather project info
    info = get_project_info(cwd)

    # Build context message
    context_parts = []

    if info["fabrik_project"]:
        context_parts.append("This is a Fabrik project. Follow Fabrik conventions:")
        context_parts.append("- Use os.getenv() for all config, never hardcode localhost")
        context_parts.append("- Base images: python:3.12-slim-bookworm (not Alpine)")
        context_parts.append("- Health endpoints must test actual dependencies")
        context_parts.append("- See AGENTS.md for full standards")

    if info["project_type"] != "unknown":
        context_parts.append(f"\nProject type: {info['project_type']}")

    if not info["has_docker"] and info["fabrik_project"]:
        context_parts.append("\n⚠️ Missing Dockerfile - needed for Coolify deployment")

    if not info["has_compose"] and info["fabrik_project"]:
        context_parts.append("⚠️ Missing compose.yaml - needed for Coolify deployment")

    if not info["has_env_example"]:
        context_parts.append("⚠️ Missing .env.example - document all environment variables")

    # Get recent changes for resume sessions
    if source == "resume":
        recent = get_recent_changes(cwd)
        if recent:
            context_parts.append(f"\nRecently modified files: {', '.join(recent[:5])}")

    # Output context (stdout goes to droid)
    if context_parts:
        print("\n".join(context_parts))

    sys.exit(0)


if __name__ == "__main__":
    main()
