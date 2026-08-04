# AFTER-EDIT: none (one-shot cache-warmer + manifest builder; consumed by microbench_coding_direct.py --difficulty)
"""Warm the LiveCodeBench whole-release cache + freeze a question_id -> difficulty manifest.

The `--difficulty` filter in microbench_coding_direct.py must select from the WHOLE release
(head-of-shard streaming saturates), but the whole release is a multi-GB download that died with
httpx.ReadTimeout at 456kB/s on 2026-08-04 (AFCL entry). This script is the fix's first half:

1. retries the full `load_code_generation_dataset()` download (HF hub resumes partial shards) with a
   generous per-read timeout, under the harness's HF_HOME (.lcb-hf-cache) so the cache lands where the
   bench looks for it;
2. writes cache/lcb_difficulty_manifest.json  ({release, built_at, counts, difficulty: {qid: level}})
   so future difficulty-filtered runs can pre-select ids without ever re-downloading.

Run OUTSIDE the bench (it is slow):  .lcb-venv/bin/python build_lcb_difficulty_manifest.py [release_v5]
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(HERE / ".lcb-hf-cache"))
# The 2026-08-04 failure was a mid-shard read timeout at ~456kB/s; the hub default (10s) is too tight
# for this route. Must be set before huggingface_hub import (read at import time).
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")

RELEASE = sys.argv[1] if len(sys.argv) > 1 else "release_v5"
OUT = HERE / "cache" / "lcb_difficulty_manifest.json"
ATTEMPTS = 6


def main() -> int:
    from lcb_runner.benchmarks.code_generation import load_code_generation_dataset

    last_err: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            print(f"[manifest] attempt {attempt}/{ATTEMPTS}: loading {RELEASE} "
                  f"(HF_HOME={os.environ['HF_HOME']})", flush=True)
            probs = load_code_generation_dataset(release_version=RELEASE)
            break
        except Exception as e:  # noqa: BLE001 — transport errors vary (httpx/urllib3/OSError)
            last_err = e
            wait = min(60, 5 * attempt)
            print(f"[manifest] attempt {attempt} failed: {type(e).__name__}: {e} "
                  f"— retrying in {wait}s (hub resumes partial shards)", flush=True)
            time.sleep(wait)
    else:
        print(f"[manifest] FAILED after {ATTEMPTS} attempts: {last_err}", flush=True)
        return 1

    diff_of = {}
    for p in probs:
        d = getattr(p, "difficulty", None)
        diff_of[str(p.question_id)] = str(getattr(d, "value", d) or "").lower()
    counts: dict[str, int] = {}
    for v in diff_of.values():
        counts[v] = counts.get(v, 0) + 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "release": RELEASE,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": counts,
        "difficulty": diff_of,
    }, indent=1))
    print(f"[manifest] OK: {len(diff_of)} problems, counts={counts} -> {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
