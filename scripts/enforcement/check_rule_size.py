#!/usr/bin/env python3
"""Check that .windsurf/rules/**/*.md files stay under the auto-load size limit.

The cap guards against an auto-loaded (glob-activated) pack injecting too much into
agent context on every match. It is a self-imposed context-budget guard, NOT a
vendor hard limit — the only real Cascade limit is on `.windsurfrules` (silent
truncation at 6,000 chars), which does not apply to these packs (95KB+ reference
catalogs ship fine via SIZE_EXEMPT). The value previously drifted (12KB → 32KB)
out of step with the documented 50KB in docs/workflows/FINAL_GATE_WORKFLOW.md;
aligned to 50KB so legitimately-comprehensive packs (e.g. core/67-file-api.md)
aren't forced to shed real rule content. Genuinely runaway packs still trip it.
"""

import sys
from pathlib import Path

MAX_SIZE_BYTES = 51200  # 50KB — auto-load context-budget guard (see module docstring)

# Exempt reference catalogs from the size cap (2026-06-13). The cap exists to
# stop AUTO-LOADED rule packs from bloating agent context. These three are not
# that: the two design systems carry NO activation frontmatter (no globs) — they
# are on-demand reference, injected by Traycer as Context Files for specific UI
# tickets, never auto-loaded; the email-templates pack is glob-scoped to
# email/template paths only. Splitting/relocating them would break ~10+ inbound
# references (CHANGELOG, kilo_dispatch.py, docs/**) for no context-bloat benefit.
SIZE_EXEMPT = {
    "core/ocoron-design-system.md",
    "core/tojlo-design-system.md",
    "core/86-email-templates.md",
}


def main() -> int:
    """Check rule file sizes (recursive — includes subdirectories)."""
    rules_dir = Path.cwd() / ".windsurf" / "rules"

    if not rules_dir.exists():
        return 0

    errors = []
    for rule_file in rules_dir.rglob("*.md"):
        relative = rule_file.relative_to(rules_dir)
        if relative.as_posix() in SIZE_EXEMPT:
            continue
        size = rule_file.stat().st_size
        if size > MAX_SIZE_BYTES:
            errors.append(f"ERROR: {relative} is {size} bytes (>{MAX_SIZE_BYTES})")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
