#!/usr/bin/env python3
"""Check port registration in PORTS.md and validate port ranges."""

import re
from pathlib import Path

# Patterns for SERVICE ports (not client connection ports)
# Matches: PORT=8000, port: 8000, EXPOSE 8000
# Excludes: DB_PORT, REDIS_PORT, etc. (client connections)
SERVICE_PORT_PATTERN = re.compile(r"(?<![A-Z_])(?:port|PORT)\s*[=:]\s*(\d{4,5})")
EXPOSE_PATTERN = re.compile(r"EXPOSE\s+(\d{4,5})")

# Port ranges per technology (from 00-critical.md)
# Only applied to service ports, not client connections
PORT_RANGES = {
    ".py": (8000, 8099, "Python services"),
    ".ts": (3000, 3099, "Frontend apps"),
    ".tsx": (3000, 3099, "Frontend apps"),
    ".js": (3000, 3099, "Frontend apps"),
}


def check_file(file_path: Path) -> list:
    """Check if ports are registered in PORTS.md."""
    from .validate_conventions import CheckResult, Severity

    results = []
    suffix = file_path.suffix.lower()
    name = file_path.name.lower()

    # Only check relevant files
    if suffix not in (".py", ".yaml", ".yml", ".ts", ".tsx", ".js") and name != "dockerfile":
        return results

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return results

    # Find ports in file (service ports only, not client connections)
    ports_found = set()
    for pattern in [SERVICE_PORT_PATTERN, EXPOSE_PATTERN]:
        for match in pattern.finditer(content):
            port = int(match.group(1))
            if 1024 < port < 65535:
                ports_found.add(port)

    if not ports_found:
        return results

    # Check if PORTS.md exists and contains these ports
    ports_md = file_path.parent / "PORTS.md"
    if not ports_md.exists():
        ports_md = Path("/opt/fabrik/PORTS.md")

    registered_ports = set()
    if ports_md.exists():
        try:
            ports_content = ports_md.read_text()
            for match in re.finditer(r"\b(\d{4,5})\b", ports_content):
                registered_ports.add(int(match.group(1)))
        except (OSError, UnicodeDecodeError):
            pass

    # Report unregistered ports
    for port in ports_found - registered_ports:
        results.append(
            CheckResult(
                check_name="ports",
                severity=Severity.WARN,
                message=f"Port {port} not found in PORTS.md",
                file_path=str(file_path),
                line_number=1,
                fix_hint=f"Register port {port} in PORTS.md to avoid conflicts",
            )
        )

    # Check port ranges per technology
    if suffix in PORT_RANGES:
        min_port, max_port, tech_name = PORT_RANGES[suffix]
        for port in ports_found:
            if not (min_port <= port <= max_port):
                results.append(
                    CheckResult(
                        check_name="ports",
                        severity=Severity.WARN,
                        message=f"Port {port} outside {tech_name} range ({min_port}-{max_port})",
                        file_path=str(file_path),
                        line_number=1,
                        fix_hint=f"Use port in range {min_port}-{max_port} for {tech_name}",
                    )
                )

    return results
