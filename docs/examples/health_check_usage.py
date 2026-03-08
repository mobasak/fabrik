#!/usr/bin/env python3
"""
Usage Examples: health_checker.py

This demonstrates how to use the health_checker.py script for:
- HTTP health endpoint checks (e.g., FastAPI /health endpoints)
- Database TCP reachability checks
- Combined health checks with custom timeouts
- Interpreting exit codes for programmatic usage

The script is designed for CI/CD automation, cron jobs, and monitoring systems.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

from health_checker import main, EXIT_OK, EXIT_HTTP_UNHEALTHY, EXIT_DB_UNREACHABLE, EXIT_CONFIG


def example_http_check():
    """Example 1: HTTP-only health check against a FastAPI /health endpoint.

    This demonstrates checking a local FastAPI service running on port 8000.
    The health endpoint should return {"status": "ok"} for success.
    """
    print("=" * 60)
    print("Example 1: HTTP Health Check Only")
    print("=" * 60)

    args = ["--health-url", "http://localhost:8000/health"]
    print(f"Running: health_checker.py {' '.join(args)}")
    print()

    exit_code = main(args)

    if exit_code == EXIT_OK:
        print("✓ HTTP check passed")
    elif exit_code == EXIT_HTTP_UNHEALTHY:
        print("✗ HTTP check failed - endpoint returned unhealthy status")
    elif exit_code == EXIT_CONFIG:
        print("✗ Configuration error")
    else:
        print(f"✗ Unexpected exit code: {exit_code}")

    print()
    return exit_code


def example_db_check():
    """Example 2: Database TCP reachability check only.

    This demonstrates checking if a PostgreSQL database is reachable via TCP.
    The script reads DB_HOST and DB_PORT from environment variables.
    """
    print("=" * 60)
    print("Example 2: Database Reachability Check Only")
    print("=" * 60)

    args = ["--check-db"]
    print(f"Running: health_checker.py {' '.join(args)}")
    print(f"DB_HOST={os.getenv('DB_HOST', 'not set')}")
    print(f"DB_PORT={os.getenv('DB_PORT', 'not set')}")
    print()

    exit_code = main(args)

    if exit_code == EXIT_OK:
        print("✓ Database is reachable")
    elif exit_code == EXIT_DB_UNREACHABLE:
        print("✗ Database is not reachable - TCP connection failed")
    elif exit_code == EXIT_CONFIG:
        print("✗ Configuration error - DB_HOST/DB_PORT not set or invalid")
    else:
        print(f"✗ Unexpected exit code: {exit_code}")

    print()
    return exit_code


def example_combined_check():
    """Example 3: Combined HTTP and DB check with custom timeout.

    This demonstrates:
    - Running both HTTP and DB checks in a single invocation
    - Customizing the timeout for network operations
    - Interpreting all possible exit codes

    Exit codes are:
    - 0 (EXIT_OK): All checks passed
    - 2 (EXIT_CONFIG): Configuration error (missing/invalid env vars or no checks requested)
    - 3 (EXIT_HTTP_UNHEALTHY): HTTP endpoint returned unhealthy status
    - 4 (EXIT_DB_UNREACHABLE): Database TCP connection failed
    """
    print("=" * 60)
    print("Example 3: Combined HTTP + DB Check with Custom Timeout")
    print("=" * 60)

    args = ["--health-url", "http://localhost:8000/health", "--check-db", "--timeout", "3.0"]
    print(f"Running: health_checker.py {' '.join(args)}")
    print()

    exit_code = main(args)

    print()
    print("Exit code interpretation:")
    print(f"  EXIT_OK (0):              {'✓' if exit_code == EXIT_OK else ' '} All checks passed")
    print(
        f"  EXIT_CONFIG (2):           {'✓' if exit_code == EXIT_CONFIG else ' '} Configuration error"
    )
    print(
        f"  EXIT_HTTP_UNHEALTHY (3):  {'✓' if exit_code == EXIT_HTTP_UNHEALTHY else ' '} HTTP check failed"
    )
    print(
        f"  EXIT_DB_UNREACHABLE (4):  {'✓' if exit_code == EXIT_DB_UNREACHABLE else ' '} DB check failed"
    )
    print(f"  Actual exit code: {exit_code}")
    print()

    return exit_code


if __name__ == "__main__":
    print("Health Checker Usage Examples")
    print("=" * 60)
    print()

    results = {
        "HTTP Check": example_http_check(),
        "DB Check": example_db_check(),
        "Combined Check": example_combined_check(),
    }

    print("=" * 60)
    print("Summary")
    print("=" * 60)
    for name, code in results.items():
        status = "✓ PASS" if code == EXIT_OK else f"✗ FAIL ({code})"
        print(f"{name:20s} {status}")
    print()
