#!/usr/bin/env python3
"""One-time script: extract real host ports from compose.yaml/.env and update project.yaml.

Reads each project's compose.yaml for port mappings and .env.example/.env for
HOST_PORT/PORT defaults. Replaces the seeded 'port: 8000' with accurate 'ports: [...]'.

Also handles the schema migration from 'port: int' to 'ports: list[int]'.

Usage:
    python scripts/seed_real_ports.py          # Dry-run (default)
    python scripts/seed_real_ports.py --apply  # Actually write changes
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

FABRIK_ROOT = Path("/opt/fabrik")
DEFAULT_EXCLUDES = {"_*", ".*", "fabrik", "__pycache__", "venv", "google"}

# Known production host ports (from PORTS.md and infrastructure knowledge)
# These are the HOST ports that bind on the machine — what causes conflicts
KNOWN_PORTS: dict[str, list[int]] = {
    "captcha": [18011],
    "translator": [18012],
    "proxy": [18013],
    "site-provisioner": [18014],
    "file-api": [18015],
    "emailgateway": [18017],
    "email-reader": [18018],
}

# Port ranges by project type
PYTHON_RANGE = (8000, 8099)
NODE_RANGE = (3000, 3099)


def _is_excluded(name: str) -> bool:
    import fnmatch

    return any(fnmatch.fnmatch(name, p) for p in DEFAULT_EXCLUDES)


def extract_ports_from_compose(project_dir: Path) -> list[int]:
    """Extract host ports from compose.yaml port mappings."""
    compose = project_dir / "compose.yaml"
    if not compose.exists():
        return []

    ports: list[int] = []
    try:
        content = compose.read_text()

        # Pattern: "${HOST_PORT:-18011}:8000" → extract 18011
        for m in re.finditer(r"HOST_PORT:-(\d+)", content):
            ports.append(int(m.group(1)))

        # Pattern: "8014:5050" or "8010:8000" (explicit host:container)
        for m in re.finditer(r'["\']?(\d{4,5}):(\d{4,5})["\']?', content):
            host_port = int(m.group(1))
            # Skip if it looks like a container-only port (same as container)
            # or if we already got it from HOST_PORT
            if host_port not in ports:
                ports.append(host_port)

    except Exception:
        pass
    return sorted(set(ports))


def extract_port_from_env(project_dir: Path) -> int | None:
    """Extract PORT or HOST_PORT from .env.example."""
    for env_file in [".env.example", ".env"]:
        f = project_dir / env_file
        if not f.exists():
            continue
        try:
            content = f.read_text()
            # Look for HOST_PORT first (more specific)
            m = re.search(r"^HOST_PORT\s*=\s*(\d+)", content, re.MULTILINE)
            if m:
                return int(m.group(1))
            # Then PORT
            m = re.search(r"^PORT\s*=\s*(\d+)", content, re.MULTILINE)
            if m:
                val = int(m.group(1))
                # Skip DB/SMTP ports that aren't service ports
                if val not in (5432, 465, 587, 25, 993, 143):
                    return val
        except Exception:
            pass
    return None


def detect_project_type(project_dir: Path) -> str:
    """Detect if project is Python or Node.js based."""
    if (project_dir / "package.json").exists():
        return "node"
    return "python"


def determine_ports(name: str, project_dir: Path, used_ports: set[int]) -> list[int]:
    """Determine the correct ports for a project."""
    # 1. Known production ports (manually verified)
    if name in KNOWN_PORTS:
        return KNOWN_PORTS[name]

    # 2. Extract from compose.yaml
    compose_ports = extract_ports_from_compose(project_dir)
    if compose_ports:
        return compose_ports

    # 3. Extract from .env
    env_port = extract_port_from_env(project_dir)
    if env_port and env_port not in used_ports:
        return [env_port]

    # 4. Auto-allocate unique port from range
    ptype = detect_project_type(project_dir)
    port_range = NODE_RANGE if ptype == "node" else PYTHON_RANGE

    for port in range(port_range[0], port_range[1] + 1):
        if port not in used_ports:
            return [port]

    return [port_range[1] + 1]  # Overflow


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed real ports into project.yaml files")
    parser.add_argument(
        "--apply", action="store_true", help="Actually write changes (default: dry-run)"
    )
    args = parser.parse_args()

    root = Path("/opt")
    used_ports: set[int] = set()
    changes: list[tuple[str, list[int], list[int]]] = []  # (name, old_ports, new_ports)

    # First pass: collect all projects and determine ports
    projects: list[tuple[str, Path]] = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or _is_excluded(d.name):
            continue
        projects.append((d.name, d))

    # Assign known ports first to reserve them
    for name, _dir in projects:
        if name in KNOWN_PORTS:
            used_ports.update(KNOWN_PORTS[name])

    # Second pass: determine ports for all projects
    for name, project_dir in projects:
        project_yaml_path = project_dir / "project.yaml"
        if not project_yaml_path.exists():
            continue

        try:
            data = yaml.safe_load(project_yaml_path.read_text()) or {}
        except Exception:
            print(f"  ⚠️  {name}: malformed project.yaml, skipping")
            continue

        # Get current port(s)
        old_ports: list[int] = []
        if "ports" in data and isinstance(data["ports"], list):
            old_ports = [int(p) for p in data["ports"]]
        elif "port" in data and data["port"]:
            old_ports = [int(data["port"])]

        # Determine new ports
        new_ports = determine_ports(name, project_dir, used_ports)
        used_ports.update(new_ports)

        if old_ports != new_ports:
            changes.append((name, old_ports, new_ports))

            if args.apply:
                # Remove old 'port' key if it exists, set 'ports'
                if "port" in data:
                    del data["port"]
                data["ports"] = new_ports

                # Preserve header comments
                original = project_yaml_path.read_text()
                header_lines = []
                for line in original.split("\n"):
                    if line.startswith("#"):
                        header_lines.append(line)
                    else:
                        break
                header = "\n".join(header_lines) + "\n\n" if header_lines else ""

                project_yaml_path.write_text(
                    header + yaml.dump(data, default_flow_style=False, sort_keys=False)
                )

    # Report
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"\n{'=' * 60}")
    print(f"Port Seeding Report ({mode})")
    print(f"{'=' * 60}")
    print(f"Total projects scanned: {len(projects)}")
    print(f"Changes needed: {len(changes)}")
    print()

    if changes:
        print(f"{'Project':<40} {'Old':>10} → {'New':>10}")
        print("-" * 65)
        for name, old_ports, new_ports in sorted(changes):
            old_str = ",".join(str(p) for p in old_ports) if old_ports else "none"
            new_str = ",".join(str(p) for p in new_ports)
            print(f"  {name:<38} {old_str:>10} → {new_str:>10}")

    if not args.apply and changes:
        print("\n⚠️  Dry-run only. Use --apply to write changes.")

    # Check for conflicts in final allocation
    port_map: dict[int, list[str]] = {}
    for proj_name, proj_dir in projects:
        proj_yaml_path = proj_dir / "project.yaml"
        if not proj_yaml_path.exists():
            continue
        try:
            proj_data = yaml.safe_load(proj_yaml_path.read_text()) or {}
            ports = proj_data.get("ports", [])
            if isinstance(ports, list):
                for p in ports:
                    port_map.setdefault(int(p), []).append(proj_name)
            elif proj_data.get("port"):
                port_map.setdefault(int(proj_data["port"]), []).append(proj_name)
        except Exception:
            pass

    conflicts = {p: names for p, names in port_map.items() if len(names) > 1}
    if conflicts:
        if args.apply:
            print("\n⚠️  Remaining conflicts after seeding:")
        else:
            print("\n⚠️  Current conflicts (will be resolved with --apply):")
        for port, names in sorted(conflicts.items()):
            print(f"  Port {port}: {', '.join(names)}")
    else:
        print("\n✅ No port conflicts detected!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
