#!/usr/bin/env python3
"""Warn when AI rule packs in .windsurf/rules/ai/*.md are >90 days unverified.

Reads each pack's `Last content verification: YYYY-MM-DD` line and prints a
warning to stdout when (today - date) > AI_PACK_STALE_DAYS. Packs without the
line are reported as "unstamped" (warning, not error). Exit 0 always — this
is a freshness signal in the daily log, not a gate.

Invoked from wsl_startup_hook.sh after the embedding pipeline, before
sync_extensions.sh.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path

FABRIK_ROOT = Path("/opt/fabrik")
AI_PACKS_DIR = FABRIK_ROOT / ".windsurf" / "rules" / "ai"
STALE_DAYS = int(os.environ.get("AI_PACK_STALE_DAYS", "90"))

VERIFICATION_RE = re.compile(
    r"Last content verification:\s*(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


def _today() -> date:
    return datetime.now(UTC).date()


def check_pack(pack_path: Path, today: date) -> tuple[str, int | None, str]:
    """Return (status, age_days, message). Status: 'fresh' | 'stale' | 'unstamped'."""
    text = pack_path.read_text(encoding="utf-8")
    match = VERIFICATION_RE.search(text)
    if not match:
        return (
            "unstamped",
            None,
            f"{pack_path.name}: no `Last content verification:` line — "
            "consider stamping to track refresh cadence",
        )
    try:
        verified = date.fromisoformat(match.group(1))
    except ValueError as e:
        return ("unstamped", None, f"{pack_path.name}: malformed date {match.group(1)!r} ({e})")
    age = (today - verified).days
    if age > STALE_DAYS:
        return (
            "stale",
            age,
            f"{pack_path.name}: verified {age} days ago "
            f"(>{STALE_DAYS}d threshold) — re-verify model lineup / vendor picks",
        )
    return ("fresh", age, f"{pack_path.name}: verified {age}d ago")


def main() -> int:
    today = _today()
    if not AI_PACKS_DIR.is_dir():
        print(f"[ai-pack-freshness] {AI_PACKS_DIR} does not exist — skipping")
        return 0

    packs = sorted(AI_PACKS_DIR.glob("*.md"))
    if not packs:
        print(f"[ai-pack-freshness] no .md files in {AI_PACKS_DIR}")
        return 0

    fresh, stale, unstamped = [], [], []
    for pack in packs:
        status, _age, msg = check_pack(pack, today)
        {"fresh": fresh, "stale": stale, "unstamped": unstamped}[status].append(msg)

    print(
        f"[ai-pack-freshness] {len(packs)} packs scanned "
        f"(threshold: {STALE_DAYS}d) on {today.isoformat()}"
    )
    if stale:
        print(f"[ai-pack-freshness] ⚠️  {len(stale)} STALE pack(s):")
        for m in stale:
            print(f"  - {m}")
    if unstamped:
        print(f"[ai-pack-freshness] ℹ️  {len(unstamped)} unstamped pack(s):")
        for m in unstamped:
            print(f"  - {m}")
    if not stale and not unstamped:
        print(f"[ai-pack-freshness] ✅ all {len(packs)} packs fresh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
