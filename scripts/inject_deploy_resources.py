#!/usr/bin/env python3
# AFTER-EDIT: none
"""F5 backfill: inject deploy.resources.limits into a service compose.yaml.

Idempotent — re-running on a compose that already has the deploy block
is a no-op. Preserves comments and original formatting elsewhere.
"""

import sys
from pathlib import Path


def inject(compose_path: Path, memory: str, cpus: str) -> str:
    """Return new compose content with the deploy block injected.

    Strategy: find the END of the single service block (right before the
    first column-0 line after `services:`), insert deploy block there
    at 4-space indent (matching the service body indent).

    Returns "noop" if already injected; "ok" if updated; raises ValueError
    on unparseable structure.
    """
    text = compose_path.read_text()
    if "deploy:" in text and "resources:" in text and "limits:" in text:
        return "noop"

    lines = text.splitlines(keepends=False)

    # Find line index of `services:` (must be column 0)
    services_idx = None
    for i, line in enumerate(lines):
        if line.rstrip() == "services:":
            services_idx = i
            break
    if services_idx is None:
        raise ValueError("No top-level 'services:' key found")

    # Find the END of the service block: first line AFTER services_idx
    # that starts in column 0 (i.e., another top-level key) OR end of file.
    end_idx = len(lines)
    for i in range(services_idx + 1, len(lines)):
        line = lines[i]
        # Skip blank lines and comments
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        # Top-level key (no leading whitespace)?
        if line and not line[0].isspace():
            end_idx = i
            break

    # Walk backwards from end_idx to skip trailing blank lines INSIDE the service
    insert_idx = end_idx
    while insert_idx > services_idx + 1 and not lines[insert_idx - 1].strip():
        insert_idx -= 1

    # Insert at indentation 4 (matches service body)
    block = [
        "    deploy:",
        "      resources:",
        "        limits:",
        f"          memory: {memory}",
        f"          cpus: '{cpus}'",
    ]
    new_lines = lines[:insert_idx] + block + [""] + lines[insert_idx:]
    return "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <compose_path> <memory> <cpus>")
        sys.exit(1)
    path = Path(sys.argv[1])
    new = inject(path, sys.argv[2], sys.argv[3])
    if new == "noop":
        print(f"NOOP {path} (already has deploy.resources)")
    else:
        path.write_text(new)
        print(f"OK   {path} (deploy.resources.limits injected)")
