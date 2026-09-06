#!/usr/bin/env python3
# AFTER-EDIT: docs/workflows/DATA_SYNC_WORKFLOW.md
"""Audit .env files across all /opt/* projects.

This script NEVER writes secrets. It produces:
1. data/env_audit.yaml — var names + metadata (no values)
2. Console warnings for violations (localhost, banned passwords, conflicts)

Usage:
    python scripts/audit_envs.py          # Run audit, print report
    python scripts/audit_envs.py --yaml   # Also write data/env_audit.yaml
    python scripts/audit_envs.py --fix    # Suggest fixes for common violations
"""

import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

FABRIK_ROOT = Path("/opt/fabrik")
AUDIT_OUTPUT = FABRIK_ROOT / "data" / "env_audit.yaml"

# Directories to skip
EXCLUDES = {
    "fabrik",
    "fabrik-lib",
    "fabrik-libs",
    "mt-router",
    "archived",
    "google",
    "containerd",
    "__pycache__",
    "venv",
}

# Banned password values (checked against actual values — never logged)
BANNED_VALUES = {"postgres", "admin", "password", "password123", "changeme", "secret"}

# Patterns indicating a variable holds a secret
SENSITIVE_PATTERNS = [
    r".*PASSWORD.*",
    r".*SECRET.*",
    r".*TOKEN.*",
    r".*_KEY$",
    r".*API_KEY.*",
    r".*PASSPHRASE.*",
    r".*DSN.*",
]

# Violations to check
LOCALHOST_VARS = {"DATABASE_URL", "DB_HOST", "REDIS_URL", "REDIS_HOST", "BROKER_URL"}


@dataclass
class EnvVar:
    """Metadata about a single env var (no value stored)."""

    name: str
    project: str
    is_sensitive: bool
    has_value: bool
    violations: list[str] = field(default_factory=list)


@dataclass
class AuditResult:
    """Complete audit result."""

    timestamp: str
    projects_scanned: int
    total_vars: int
    violations: list[str]
    conflicts: dict[str, list[str]]  # var_name → [projects using it]
    vars_by_project: dict[str, list[dict]]


def is_sensitive(var_name: str) -> bool:
    """Check if var name indicates a secret."""
    return any(re.match(p, var_name, re.IGNORECASE) for p in SENSITIVE_PATTERNS)


def parse_env_names(env_path: Path) -> list[tuple[str, str]]:
    """Parse .env file, return list of (var_name, value) tuples.

    Values are needed for violation checks but NEVER written to output.
    """
    if not env_path.exists():
        return []

    results = []
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if match:
            var_name = match.group(1)
            value = match.group(2).strip('"').strip("'")
            results.append((var_name, value))
    return results


def check_violations(var_name: str, value: str) -> list[str]:
    """Check a var for common violations. Never logs the value itself."""
    violations = []

    # Localhost in connection strings
    if var_name in LOCALHOST_VARS or var_name.endswith("_URL") or var_name.endswith("_HOST"):
        if "localhost" in value or "127.0.0.1" in value:
            violations.append("localhost-in-connection-string")

    # Banned passwords
    if is_sensitive(var_name) and value.lower() in BANNED_VALUES:
        violations.append("banned-password-value")

    # Empty sensitive var
    if is_sensitive(var_name) and not value:
        violations.append("empty-secret")

    # Short password (< 16 chars for PASSWORD/SECRET vars)
    if re.match(r".*(PASSWORD|SECRET).*", var_name, re.IGNORECASE):
        if value and len(value) < 16:
            violations.append("short-secret")

    return violations


def scan_all_projects() -> AuditResult:
    """Scan all /opt/* projects and produce audit result."""
    opt = Path("/opt")
    all_vars: list[EnvVar] = []
    var_to_projects: dict[str, list[str]] = defaultdict(list)
    violations: list[str] = []
    vars_by_project: dict[str, list[dict]] = {}
    projects_scanned = 0

    for project_dir in sorted(opt.iterdir()):
        if not project_dir.is_dir():
            continue
        if project_dir.name.startswith(("_", ".")):
            continue
        if project_dir.name in EXCLUDES:
            continue

        env_file = project_dir / ".env"
        if not env_file.exists():
            continue

        projects_scanned += 1
        project_name = project_dir.name
        project_vars = []

        for var_name, value in parse_env_names(env_file):
            var_violations = check_violations(var_name, value)
            sensitive = is_sensitive(var_name)

            env_var = EnvVar(
                name=var_name,
                project=project_name,
                is_sensitive=sensitive,
                has_value=bool(value),
                violations=var_violations,
            )
            all_vars.append(env_var)
            var_to_projects[var_name].append(project_name)

            # Record violations with context
            for v in var_violations:
                violations.append(f"{project_name}/{var_name}: {v}")

            project_vars.append(
                {
                    "name": var_name,
                    "sensitive": sensitive,
                    "has_value": bool(value),
                    "violations": var_violations or None,
                }
            )

        vars_by_project[project_name] = project_vars

    # Detect conflicts (same var name in 3+ projects with potentially different semantics)
    # Common vars like DATABASE_URL are expected — only flag truly conflicting ones
    conflicts = {}
    for var_name, projects in var_to_projects.items():
        if len(projects) >= 3 and var_name not in {
            "DATABASE_URL",
            "REDIS_URL",
            "DB_HOST",
            "DB_PORT",
            "DB_NAME",
            "LOG_LEVEL",
            "NODE_ENV",
            "ENVIRONMENT",
            "PORT",
            "HOST",
            "DEBUG",
            "TZ",
            "GLITCHTIP_DSN",
            "SERVICE_INTERNAL_SECRET_KEY",
        }:
            conflicts[var_name] = projects

    return AuditResult(
        timestamp=datetime.now().isoformat(),
        projects_scanned=projects_scanned,
        total_vars=len(all_vars),
        violations=violations,
        conflicts=conflicts,
        vars_by_project=vars_by_project,
    )


def write_audit_yaml(result: AuditResult) -> None:
    """Write audit results to data/env_audit.yaml (names only, zero secrets)."""
    AUDIT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "version": 1,
        "timestamp": result.timestamp,
        "projects_scanned": result.projects_scanned,
        "total_vars": result.total_vars,
        "violation_count": len(result.violations),
        "violations": result.violations or None,
        "conflicts": result.conflicts or None,
        "projects": result.vars_by_project,
    }

    AUDIT_OUTPUT.write_text(
        "# Env audit — var names only, zero secrets\n"
        "# Auto-generated by scripts/audit_envs.py\n"
        + yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def print_report(result: AuditResult) -> None:
    """Print human-readable audit report."""
    print(f"Env Audit — {result.timestamp}")
    print(f"  Projects scanned: {result.projects_scanned}")
    print(f"  Total variables: {result.total_vars}")
    print(f"  Violations: {len(result.violations)}")
    print(f"  Conflicts: {len(result.conflicts)}")

    if result.violations:
        print("\nViolations:")
        for v in result.violations:
            print(f"  - {v}")

    if result.conflicts:
        print("\nConflicts (same var in 3+ projects, non-standard):")
        for var_name, projects in result.conflicts.items():
            print(f"  - {var_name}: {', '.join(projects)}")

    if not result.violations and not result.conflicts:
        print("\nAll clear.")


def main() -> int:
    """Run env audit."""
    result = scan_all_projects()
    print_report(result)

    if "--yaml" in sys.argv or "--fix" in sys.argv:
        write_audit_yaml(result)
        print(f"\nAudit written to: {AUDIT_OUTPUT}")

    if "--fix" in sys.argv and result.violations:
        print("\nSuggested fixes:")
        for v in result.violations:
            if "localhost-in-connection-string" in v:
                project, var = v.split("/")[0], v.split("/")[1].split(":")[0]
                print(
                    f"  {project}: Change {var} to use Docker service name (postgres-main/redis-main)"
                )
            elif "banned-password-value" in v:
                print(
                    f"  {v.split(':')[0]}: Generate with: python -c \"import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(32)))\""
                )
            elif "short-secret" in v:
                print(f"  {v.split(':')[0]}: Increase to 32+ chars")

    return 1 if result.violations else 0


if __name__ == "__main__":
    sys.exit(main())
