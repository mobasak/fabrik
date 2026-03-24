#!/usr/bin/env python3
"""
Acknowledge pending code reviews - moves them to acknowledged folder.

Usage:
    python3 scripts/acknowledge_reviews.py --all     # Acknowledge all
    python3 scripts/acknowledge_reviews.py --list    # List pending
    python3 scripts/acknowledge_reviews.py FILE      # Acknowledge specific
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

FABRIK_ROOT = Path(os.getenv("FABRIK_ROOT", "/opt/fabrik"))
REVIEW_RESULTS = FABRIK_ROOT / ".droid" / "reviews" / "pending"
REVIEW_ACKNOWLEDGED = FABRIK_ROOT / ".droid" / "reviews" / "acknowledged"


def list_pending() -> list[Path]:
    """List all pending reviews."""
    if not REVIEW_RESULTS.exists():
        return []
    return sorted(REVIEW_RESULTS.glob("*.json"))


def acknowledge(review_file: Path) -> bool:
    """Move review to acknowledged folder."""
    try:
        REVIEW_ACKNOWLEDGED.mkdir(parents=True, exist_ok=True)
        ack_file = REVIEW_ACKNOWLEDGED / review_file.name
        review_file.rename(ack_file)
        print(f"✓ Acknowledged: {review_file.name}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Acknowledge pending reviews")
    parser.add_argument("--all", action="store_true", help="Acknowledge all pending")
    parser.add_argument("--list", action="store_true", help="List pending reviews")
    parser.add_argument("file", nargs="?", help="Specific review file to acknowledge")
    args = parser.parse_args()

    pending = list_pending()

    if args.list or (not args.all and not args.file):
        if not pending:
            print("No pending reviews")
            return 0
        print(f"Pending reviews ({len(pending)}):")
        for f in pending:
            try:
                data = json.loads(f.read_text())
                print(f"  - {f.name}: {data.get('file_path', 'unknown')}")
            except (json.JSONDecodeError, OSError):
                print(f"  - {f.name}: (unreadable)")
        return 0

    if args.all:
        count = 0
        for f in pending:
            if acknowledge(f):
                count += 1
        print(f"Acknowledged {count}/{len(pending)} reviews")
        return 0

    if args.file:
        target = REVIEW_RESULTS / args.file
        if not target.exists():
            print(f"Not found: {args.file}", file=sys.stderr)
            return 1
        return 0 if acknowledge(target) else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
