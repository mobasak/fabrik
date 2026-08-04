"""Enforcement check: every host port referenced in compose.yaml must be registered in PORTS.txt.

Exit 0 = compliant, exit 1 = violation. Registry line format: "<port> <service>".
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def registered_ports(registry: str) -> set:
    ports = set()
    for line in registry.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ports.add(line.split()[0])
    return ports


def compose_ports(compose: str) -> list[int]:
    # matches '- "8016:8016"' / '- 8016:8016'
    return [int(m.group(1)) for m in re.finditer(r'-\s*"?(\d+):\d+"?', compose)]


def main() -> int:
    compose = (ROOT / "compose.yaml").read_text()
    registry = (ROOT / "PORTS.txt").read_text()
    reg = registered_ports(registry)
    bad = [p for p in compose_ports(compose) if p not in reg]
    if bad:
        print(f"unregistered host ports: {bad}")
        return 1
    print("ports ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
