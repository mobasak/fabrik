#!/usr/bin/env python3
"""
Fabrik Review Worker - Processes queued code reviews asynchronously.

Runs as a background process or cron job. Processes reviews queued by
fabrik-code-review.py hook and writes results for SessionStart to read.

Usage:
    python3 scripts/review_worker.py              # Process once
    python3 scripts/review_worker.py --watch      # Watch mode (continuous)
    python3 scripts/review_worker.py --daemon     # Run as daemon
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Directories
FABRIK_ROOT = Path(os.getenv("FABRIK_ROOT", "/opt/fabrik"))
REVIEW_QUEUE = FABRIK_ROOT / ".droid" / "reviews" / "queue"
REVIEW_RESULTS = FABRIK_ROOT / ".droid" / "reviews" / "pending"
REVIEW_DONE = FABRIK_ROOT / ".droid" / "reviews" / "done"

# Review settings
REVIEW_MODEL = os.getenv("FABRIK_REVIEW_MODEL", "gemini-3-flash-preview")
REVIEW_TIMEOUT = int(os.getenv("FABRIK_REVIEW_TIMEOUT", "120"))


def setup_dirs() -> None:
    """Ensure all directories exist."""
    for d in [REVIEW_QUEUE, REVIEW_RESULTS, REVIEW_DONE]:
        d.mkdir(parents=True, exist_ok=True)


def get_pending_reviews() -> list[Path]:
    """Get list of pending review files."""
    if not REVIEW_QUEUE.exists():
        return []
    return sorted(REVIEW_QUEUE.glob("*.json"))


def run_review(file_path: str, content_hash: int) -> dict:
    """Run droid exec review on a file."""
    prompt = f"""Review this file for Fabrik conventions. Check:
1. Hardcoded localhost/127.0.0.1 (should use os.getenv)
2. Hardcoded secrets/credentials
3. Health endpoints that don't test dependencies
4. Alpine base images (should use bookworm-slim)
5. Missing HEALTHCHECK in Dockerfile
6. Ports outside assigned ranges

File: {file_path}

Output JSON:
{{
  "status": "pass" | "issues_found",
  "issues": [
    {{"line": N, "severity": "error"|"warn", "message": "...", "fix": "..."}}
  ],
  "summary": "Brief summary"
}}"""

    try:
        result = subprocess.run(
            [
                "droid",
                "exec",
                "--auto",
                "low",
                "-m",
                REVIEW_MODEL,
                "-o",
                "json",
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=REVIEW_TIMEOUT,
            cwd=Path(file_path).parent if Path(file_path).exists() else FABRIK_ROOT,
        )

        if result.returncode == 0:
            # Try to parse the result
            try:
                data = json.loads(result.stdout)
                return {
                    "status": "completed",
                    "model": REVIEW_MODEL,
                    "result": data.get("result", result.stdout[:2000]),
                }
            except json.JSONDecodeError:
                return {
                    "status": "completed",
                    "model": REVIEW_MODEL,
                    "result": result.stdout[:2000],
                }
        else:
            return {
                "status": "error",
                "error": result.stderr[:500],
            }

    except subprocess.TimeoutExpired:
        return {"status": "timeout", "timeout": REVIEW_TIMEOUT}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def process_review(queue_file: Path) -> bool:
    """Process a single review from the queue."""
    try:
        data = json.loads(queue_file.read_text())
        file_path = data.get("file_path", "")
        content_hash = data.get("content_hash", 0)

        print(f"[review-worker] Processing: {file_path}")

        # Run the review
        review_result = run_review(file_path, content_hash)

        # Write result to pending (for SessionStart to read)
        result_file = (
            REVIEW_RESULTS
            / f"review_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{Path(file_path).name}.json"
        )
        result_file.write_text(
            json.dumps(
                {
                    "file_path": file_path,
                    "queued_at": data.get("queued_at"),
                    "reviewed_at": datetime.now().isoformat(),
                    "review": review_result,
                },
                indent=2,
            )
        )

        # Move queue file to done
        done_file = REVIEW_DONE / queue_file.name
        queue_file.rename(done_file)

        print(f"[review-worker] Completed: {file_path} → {result_file.name}")
        return True

    except Exception as e:
        print(f"[review-worker] Error processing {queue_file}: {e}", file=sys.stderr)
        return False


def process_all() -> int:
    """Process all pending reviews. Returns count processed."""
    setup_dirs()
    pending = get_pending_reviews()

    if not pending:
        print("[review-worker] No pending reviews")
        return 0

    processed = 0
    for queue_file in pending:
        if process_review(queue_file):
            processed += 1

    print(f"[review-worker] Processed {processed}/{len(pending)} reviews")
    return processed


def watch_mode(interval: int = 30) -> None:
    """Watch for new reviews continuously."""
    print(f"[review-worker] Watch mode started (interval: {interval}s)")
    while True:
        process_all()
        time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fabrik Review Worker")
    parser.add_argument("--watch", action="store_true", help="Watch mode (continuous)")
    parser.add_argument("--interval", type=int, default=30, help="Watch interval (seconds)")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    args = parser.parse_args()

    if args.daemon:
        # Daemonize
        if os.fork() > 0:
            sys.exit(0)
        os.setsid()
        if os.fork() > 0:
            sys.exit(0)
        watch_mode(args.interval)
    elif args.watch:
        watch_mode(args.interval)
    else:
        process_all()

    return 0


if __name__ == "__main__":
    sys.exit(main())
