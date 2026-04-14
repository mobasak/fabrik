#!/usr/bin/env python3
"""Check Docker conventions (base images, healthcheck, port consistency)."""

import re
from pathlib import Path

ALPINE_PATTERN = re.compile(r"FROM\s+.*alpine", re.IGNORECASE)
HEALTHCHECK_PATTERN = re.compile(r"HEALTHCHECK", re.IGNORECASE)
EXPOSE_PATTERN = re.compile(r"EXPOSE\s+(\d+)", re.IGNORECASE)
COMPOSE_PORT_PATTERN = re.compile(r'["\']\$\{?PORT[^}]*\}?:(\d+)["\']|["\'](\d+):(\d+)["\']')

APPROVED_BASES = [
    "python:3.12-slim-bookworm",
    "python:3.13-slim-bookworm",
    "node:22-bookworm-slim",
    "debian:bookworm-slim",
    "ubuntu:24.04",
]

# Pattern to detect Alpine in compose image: directives (including -alpine tags)
COMPOSE_ALPINE_PATTERN = re.compile(r"image:\s*['\"]?(?:alpine|[^'\"\s]*-alpine)", re.IGNORECASE)


def check_compose_arm64(file_path: Path) -> list:
    """Check compose.yaml for amd64 platform specification."""
    from .validate_conventions import CheckResult, Severity

    results = []
    name = file_path.name.lower()

    # Only check compose files
    if name not in ("compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"):
        return results

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return results

    # Check if file has build: directive (custom images)
    if "build:" not in content:
        return results  # Pre-built images only, skip platform check

    # Check for platform: linux/amd64
    if "platform: linux/amd64" not in content and "platform:" not in content:
        results.append(
            CheckResult(
                check_name="docker_arm64",
                severity=Severity.ERROR,
                message="Missing 'platform: linux/amd64' in compose file with build directive",
                file_path=str(file_path),
                line_number=1,
                fix_hint="Add 'platform: linux/amd64' under services"
                " that use build: (VPS is x86_64)",
            )
        )
    elif "platform:" in content and "linux/amd64" not in content:
        # Has platform but wrong value
        line_num = 1
        for i, line in enumerate(content.splitlines(), 1):
            if "platform:" in line.lower():
                line_num = i
                break
        results.append(
            CheckResult(
                check_name="docker_arm64",
                severity=Severity.ERROR,
                message="Platform specified but not amd64-compatible (VPS requires linux/amd64)",
                file_path=str(file_path),
                line_number=line_num,
                fix_hint="Change to 'platform: linux/amd64'",
            )
        )

    return results


def check_file(file_path: Path) -> list:
    """Check Docker files for convention violations."""
    from .validate_conventions import CheckResult, Severity

    results = []
    name = file_path.name.lower()

    # Check compose files for amd64 and Alpine images
    if name in ("compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"):
        results.extend(check_compose_arm64(file_path))
        # Check for Alpine images in compose files
        try:
            content = file_path.read_text(encoding="utf-8")
            if COMPOSE_ALPINE_PATTERN.search(content):
                line_num = 1
                for i, line in enumerate(content.splitlines(), 1):
                    if COMPOSE_ALPINE_PATTERN.search(line):
                        line_num = i
                        break
                results.append(
                    CheckResult(
                        check_name="docker",
                        severity=Severity.ERROR,
                        message="Alpine image detected in compose file."
                        " Use Debian/Ubuntu slim-bookworm.",
                        file_path=str(file_path),
                        line_number=line_num,
                        fix_hint="Use debian:bookworm-slim or specific -bookworm-slim variants",
                    )
                )
        except (OSError, UnicodeDecodeError):
            pass
        return results

    # Only check Dockerfiles for the rest
    if name != "dockerfile" and not name.endswith(".dockerfile"):
        return results

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return results

    # Check for Alpine base image
    if ALPINE_PATTERN.search(content):
        line_num = 1
        for i, line in enumerate(content.splitlines(), 1):
            if ALPINE_PATTERN.search(line):
                line_num = i
                break
        results.append(
            CheckResult(
                check_name="docker",
                severity=Severity.ERROR,
                message="Alpine base image detected. Use Debian/Ubuntu slim-bookworm.",
                file_path=str(file_path),
                line_number=line_num,
                fix_hint="Use python:3.12-slim-bookworm or node:22-bookworm-slim",
            )
        )

    # Check for HEALTHCHECK instruction
    if not HEALTHCHECK_PATTERN.search(content):
        results.append(
            CheckResult(
                check_name="docker",
                severity=Severity.WARN,
                message="No HEALTHCHECK instruction found",
                file_path=str(file_path),
                line_number=1,
                fix_hint=(
                    "Add: HEALTHCHECK --interval=30s"
                    " CMD curl -f http://localhost:${PORT:-8000}/health || exit 1"
                ),
            )
        )

    # Check port consistency with compose.yaml
    expose_match = EXPOSE_PATTERN.search(content)
    if expose_match:
        dockerfile_port = expose_match.group(1)
        project_root = file_path.parent

        compose_file = project_root / "compose.yaml"
        if not compose_file.exists():
            compose_file = project_root / "compose.yml"

        if compose_file.exists():
            try:
                compose_content = compose_file.read_text(encoding="utf-8")
                compose_ports = set()

                for match in COMPOSE_PORT_PATTERN.finditer(compose_content):
                    # Extract container port from various patterns
                    port = match.group(1) or match.group(3)
                    if port:
                        compose_ports.add(port)

                if compose_ports and dockerfile_port not in compose_ports:
                    results.append(
                        CheckResult(
                            check_name="docker_ports",
                            severity=Severity.WARN,
                            message=(
                                f"Dockerfile EXPOSE {dockerfile_port}"
                                " not found in compose.yaml ports"
                            ),
                            file_path=str(file_path),
                            fix_hint=(
                                f"Ensure compose.yaml uses port {dockerfile_port} or update EXPOSE"
                            ),
                        )
                    )
            except (OSError, UnicodeDecodeError):
                pass

    return results
