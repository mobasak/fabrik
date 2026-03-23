#!/usr/bin/env python3
"""Enforce compose.yaml service documentation.

When new services are added to compose.yaml, they should be documented
in SERVICES.md or the project README.

Triggers on:
- Changes to compose.yaml, compose.yml, docker-compose.yaml, docker-compose.yml
- New service definitions added

Enforces (WARNING only):
- New services documented in docs/SERVICES.md or README.md

Exit codes:
    0 - Pass (always - warnings only)
"""

import re
import subprocess
import sys
from pathlib import Path


def get_staged_files() -> list[str]:
    """Get list of staged files."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--cached", "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True,
            text=True,
        )
    return result.stdout.strip().split("\n") if result.stdout.strip() else []


def get_new_services(filepath: str) -> set[str]:
    """Extract new service names from compose file diff."""
    services = set()
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", filepath],
            capture_output=True,
            text=True,
        )
        diff_content = result.stdout

        in_services_block = False
        for line in diff_content.split("\n"):
            if line.startswith("+") and "services:" in line:
                in_services_block = True
                continue

            if in_services_block and line.startswith("+"):
                match = re.match(r"^\+\s{2}([a-z][a-z0-9_-]*):\s*$", line)
                if match:
                    services.add(match.group(1))

                if (
                    line.startswith("+")
                    and not line.startswith("+ ")
                    and ":" in line
                    and not line.strip().startswith("#")
                ):
                    in_services_block = False

    except (OSError, subprocess.SubprocessError):
        pass
    return services


def service_documented(service_name: str) -> bool:
    """Check if service is documented in SERVICES.md or README.md."""
    doc_files = [
        Path("docs/SERVICES.md"),
        Path("SERVICES.md"),
        Path("README.md"),
        Path("docs/README.md"),
    ]

    for doc_file in doc_files:
        if doc_file.exists():
            try:
                content = doc_file.read_text().lower()
                if service_name.lower() in content:
                    return True
            except (OSError, UnicodeDecodeError):
                pass

    return False


def is_compose_file(filepath: str) -> bool:
    """Check if file is a Docker Compose file."""
    name = Path(filepath).name.lower()
    return name in (
        "compose.yaml",
        "compose.yml",
        "docker-compose.yaml",
        "docker-compose.yml",
    )


def main() -> int:
    """Check compose.yaml service documentation."""
    staged_files = get_staged_files()

    if not staged_files or staged_files == [""]:
        return 0

    compose_files = [f for f in staged_files if is_compose_file(f)]

    if not compose_files:
        print("✅ Compose services check PASSED (no compose files)")
        return 0

    all_new_services: set[str] = set()
    for compose_file in compose_files:
        new_services = get_new_services(compose_file)
        all_new_services.update(new_services)

    if not all_new_services:
        print("✅ Compose services check PASSED (no new services)")
        return 0

    undocumented = [s for s in all_new_services if not service_documented(s)]

    if not undocumented:
        print("✅ Compose services check PASSED (all services documented)")
        return 0

    print("WARNING: New Docker services not documented:")
    print("")
    for service in sorted(undocumented):
        print(f"  - {service}")
    print("")
    print("Recommendation:")
    print("  Document these services in docs/SERVICES.md or README.md:")
    print("  - Service name and purpose")
    print("  - Port mappings")
    print("  - Required environment variables")
    print("  - Health check endpoint")
    print("")
    print("(This is a WARNING - commit will proceed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
