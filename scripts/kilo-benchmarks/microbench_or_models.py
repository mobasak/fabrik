#!/usr/bin/env python3
"""
Microbench every active OR-routed LLM model for output_tokens_per_sec + ttft_ms.

Design rationale (from docs/development/plans/2026-07-02-plan-1-speed-coverage.md
Phase 2): AA leaderboard only covers ~166 models. To close the coverage gap
on the long tail, call each unbenched model via OR's streaming API with a
fixed prompt, measure TTFT + TPS, and take the median of 3 runs.

Cost is capped by a $10/run stop-before-next kill switch: after each
call's `usage.cost` gets added to the running sum, if we've crossed
the cap the loop breaks before the NEXT call. Real max overrun is
one bench's cost (~$0.001-$0.05 realistic worst-case with the cohort
filter) — we cannot refund a call already in flight. OR's streaming
response carries `usage.cost` (actual billed USD) when
`usage.include=true`, so the cap uses real spend not headline-price
estimates.

Weekly cadence (invoked from daily_refresh.sh Sunday-only). Idempotent —
rows benched within the last 30 days are skipped without API calls.

Usage:
    python microbench_or_models.py                   # bench + update DB
    python microbench_or_models.py --dry-run         # cohort + est cost only
    python microbench_or_models.py --limit 5         # cap models per run
    python microbench_or_models.py --cost-cap 3      # override $10 hard cap

Environment:
    OPENROUTER_API_KEY  required; script exits 0 (non-fatal) if missing

Cost-budget note: this script does NOT vendor fabrik-lib's cost-budget/
module (that's a production LLM-caller pattern with PG cost_ledger + WAL
— overkill for a weekly batch). The in-script running-sum cost tracker
with a hard $10 exit gate is proportional. A future migration to
cost-budget/ is a one-file swap: replace `_check_cost_cap` + `_log_cost`
with the module's `check_caps()` / `record_cost()` calls.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import statistics
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
CACHE_DIR = SCRIPT_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
LOG_PATH = CACHE_DIR / "microbench_log.jsonl"

OR_URL = "https://openrouter.ai/api/v1/chat/completions"
BENCH_PROMPT = (
    "Write exactly a 200-word explanation of how gears mesh in a "
    "mechanical clock. Do not use markdown."
)
MAX_TOKENS = 300
TEMPERATURE = 0.2
REQ_TIMEOUT_S = 90
RATE_LIMIT_SLEEP_S = 0.5  # 2 req/s ceiling
COST_CAP_USD = 10.0
RECENCY_WINDOW_DAYS = 30
BENCH_N_RUNS = 3  # median-of-3

SPEED_SOURCE_PREFIX = "own_microbench"


def log(msg: str) -> None:
    print(f"[microbench] {msg}", flush=True)


# ---------- SSE stream parser ----------


def _parse_stream(resp: requests.Response, t0: float) -> dict:
    """Consume OR's SSE stream and compute (tps, ttft_ms, cost_usd).

    Returns `{tps, ttft_ms, prompt_tokens, completion_tokens, cost_usd,
    error}`. `error` is None on success, string on failure.

    TTFT = time from `t0` (moment the caller issued `requests.post`, per the
    industry-standard definition — round-trip + provider queue + prefill) to
    the first `data:` chunk whose `delta.content` is non-empty (the first
    delta often carries `role:"assistant"` with empty content — skip).

    Do NOT compute `t0` inside this function: by the time it's called the
    HTTP round-trip already completed and the buffer may already hold the
    entire response, producing 1-3 ms readings that measure Python overhead
    only — not network + provider latency (fixed 2026-07-11).

    TPS = completion_tokens / (t_last_content_chunk - t_first_content_chunk).
    """
    t_first_content = None
    t_last_content = None
    usage_block = None

    try:
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith(":"):
                continue  # ": OPENROUTER PROCESSING" keepalive
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue  # skip malformed line, keep parsing

            # Content chunk? Reasoning models (gpt-5, o1/o3, R1, QwQ, arcee,
            # nemotron-nano) emit content="" and put tokens in delta.reasoning;
            # usage.completion_tokens counts reasoning + content, so timing
            # from first-any-chunk to last-any-chunk keeps TPS math consistent.
            # OpenAI o-family also mirrors tokens in delta.reasoning_details
            # (array of {type, summary/text, ...}) — extract as belt-and-suspenders
            # in case some model returns ONLY reasoning_details without reasoning.
            choices = obj.get("choices") or []
            if choices:
                delta = (choices[0] or {}).get("delta") or {}
                content = (delta.get("content") or "") + (delta.get("reasoning") or "")
                if not content:
                    details = delta.get("reasoning_details") or []
                    content = "".join(
                        (d.get("summary") or d.get("text") or "")
                        for d in details
                        if isinstance(d, dict)
                    )
                if content:
                    now = time.monotonic()
                    if t_first_content is None:
                        t_first_content = now
                    t_last_content = now

            # Final chunk with usage?
            if obj.get("usage"):
                usage_block = obj["usage"]
    except (
        requests.exceptions.RequestException,
        ConnectionError,
        # A mangling proxy or partial-multibyte chunk from OR/CDN can send
        # non-UTF-8 bytes mid-stream — iter_lines(decode_unicode=True) then
        # raises. Without this catch the whole weekly run would crash
        # instead of skipping just this model. (Review finding 2026-07-02.)
        UnicodeDecodeError,
    ) as e:
        return _err(f"stream error: {e}")

    if usage_block is None:
        return _err("no usage block in stream")
    if t_first_content is None or t_last_content is None:
        return _err("no content chunks in stream")

    completion_tokens = int(usage_block.get("completion_tokens") or 0)
    if completion_tokens <= 0:
        return _err(f"zero completion_tokens (usage={usage_block})")

    stream_duration = t_last_content - t_first_content
    if stream_duration <= 0:
        # Single-chunk stream — first and last content chunk are the same.
        # Fast providers (Cerebras, Groq LPU via OR routing, small responses)
        # deliver all completion tokens in one chunk. We cannot compute TPS
        # from a single sample without fabricating; return an error so the
        # bench is skipped instead of writing nonsense (fixed by review
        # 2026-07-02 — earlier fallback of 0.1s inflated TPS 10x-30x).
        return _err(
            f"single-chunk stream — TPS unmeasurable "
            f"(completion_tokens={completion_tokens}, duration=0)"
        )
    tps = completion_tokens / stream_duration
    ttft_ms = (t_first_content - t0) * 1000.0
    cost = float(usage_block.get("cost") or 0.0)

    return {
        "tps": round(tps, 2),
        "ttft_ms": round(ttft_ms, 1),
        "prompt_tokens": int(usage_block.get("prompt_tokens") or 0),
        "completion_tokens": completion_tokens,
        "cost_usd": round(cost, 8),
        "error": None,
    }


def _err(msg: str) -> dict:
    return {
        "tps": None,
        "ttft_ms": None,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cost_usd": 0.0,
        "error": msg,
    }


# ---------- Bench primitives ----------


def bench_one(model_id: str, api_key: str) -> dict:
    """One microbench call. Returns dict from `_parse_stream`."""
    body = {
        "model": model_id,
        "messages": [{"role": "user", "content": BENCH_PROMPT}],
        "stream": True,
        "usage": {"include": True},
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    # t0 must bracket the network round-trip — see _parse_stream docstring.
    t0 = time.monotonic()
    try:
        resp = requests.post(OR_URL, headers=headers, json=body, stream=True, timeout=REQ_TIMEOUT_S)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
        return _err(f"request error: {e}")
    # Use as-context so the underlying HTTP connection is returned to the
    # pool even if _parse_stream raises (leak surfaced by review 2026-07-02).
    with resp:
        if resp.status_code >= 500:
            return _err(f"HTTP {resp.status_code}")
        if resp.status_code >= 400:
            try:
                body_text = resp.text[:300]
            except Exception:  # noqa: BLE001
                body_text = "?"
            return _err(f"HTTP {resp.status_code}: {body_text}")
        return _parse_stream(resp, t0)


def bench_median(model_id: str, api_key: str, n: int = BENCH_N_RUNS) -> dict:
    """Call `bench_one` n times, take median of tps + ttft_ms. Aggregate cost.

    Skips model (returns error) if 2 of n calls fail.
    """
    attempts = []
    total_cost = 0.0
    fail_count = 0
    for i in range(n):
        r = bench_one(model_id, api_key)
        total_cost += r["cost_usd"]
        if r["error"]:
            fail_count += 1
        else:
            attempts.append(r)
        if fail_count >= 2:
            return {
                "tps": None,
                "ttft_ms": None,
                "cost_usd": round(total_cost, 8),
                "error": f"{fail_count}/{i + 1} calls failed",
                "attempts": [],
            }
        # Rate-limit between calls (not before first, not after last)
        if i < n - 1:
            time.sleep(RATE_LIMIT_SLEEP_S)

    if not attempts:
        return {
            "tps": None,
            "ttft_ms": None,
            "cost_usd": round(total_cost, 8),
            "error": "all attempts failed",
            "attempts": [],
        }
    return {
        "tps": round(statistics.median(a["tps"] for a in attempts), 2),
        "ttft_ms": round(statistics.median(a["ttft_ms"] for a in attempts), 1),
        "cost_usd": round(total_cost, 8),
        "error": None,
        "attempts": attempts,
    }


# ---------- Cohort selection ----------


def _select_cohort(conn: sqlite3.Connection) -> list[dict]:
    """Rows eligible for microbench per plan Phase 2 Design filters.

    Cutoff uses `datetime.now(UTC).date()` to match `_write_result` which
    writes `speed_updated_at` as a UTC date. Local `date.today()` would
    drift by ±1 day depending on wall-clock time (bug caught by review
    2026-07-02: operator TZ is +0300; at 02:30 UTC the two dates differ).
    """
    cutoff = (datetime.now(UTC).date() - timedelta(days=RECENCY_WINDOW_DAYS)).isoformat()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, input_cost_per_m, output_cost_per_m, speed_source, speed_updated_at
        FROM agents
        WHERE status = 'active'
          AND service_type = 'llm'
          AND input_cost_per_m IS NOT NULL AND input_cost_per_m > 0
          AND output_cost_per_m IS NOT NULL AND output_cost_per_m > 0
          AND input_cost_per_m <= 200
          AND id NOT LIKE 'openrouter/%'
          AND (
            output_tokens_per_sec IS NULL
            OR (speed_source LIKE 'own_microbench%'
                AND (speed_updated_at IS NULL OR speed_updated_at < ?))
          )
        ORDER BY input_cost_per_m ASC
        """,
        (cutoff,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------- DB writer ----------


def _write_result(db_path: Path, agent_id: str, result: dict) -> bool:
    """Open a fresh short-lived connection per write.

    WSL2 filesystem behavior 2026-07-02: a long-lived sqlite connection
    that idles for 30-60s during a streaming model call can lose write
    privilege on the underlying file handle (SQLITE_READONLY on next
    UPDATE) even though the file is 644 and the process owns it. A
    per-write connection sidesteps the issue at negligible cost (<1ms
    per open vs. seconds per model call).

    Returns True on success, False on write failure — caller treats
    write failures as non-fatal (row left with prior speed_source, gets
    retried on the next cron run).
    """
    today = datetime.now(UTC).date().isoformat()
    tag = f"{SPEED_SOURCE_PREFIX} {today}"
    try:
        with sqlite3.connect(db_path, timeout=30.0) as conn:
            conn.execute(
                "UPDATE agents SET "
                "output_tokens_per_sec = ?, "
                "ttft_ms = ?, "
                "speed_source = ?, "
                "speed_updated_at = ? "
                "WHERE id = ? "
                "AND (speed_source IS NULL OR speed_source LIKE 'own_microbench%'"
                "     OR speed_source LIKE 'groq_lpu%')",
                (result["tps"], result["ttft_ms"], tag, today, agent_id),
            )
        return True
    except sqlite3.OperationalError as e:
        log(f"  → WRITE-FAIL: {e} (row unchanged, will retry next cron)")
        return False


# ---------- Run log ----------


def _append_log(entry: dict) -> None:
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


# ---------- Main loop ----------


def run_microbench(
    db_path: Path = DB_PATH,
    cost_cap_usd: float = COST_CAP_USD,
    dry_run: bool = False,
    limit: int | None = None,
) -> int:
    """Bench the eligible cohort; return exit code (0 success, 1 error)."""
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        log("SKIP: OPENROUTER_API_KEY not set")
        return 0  # non-fatal for daily_refresh

    conn = sqlite3.connect(db_path)
    try:
        cohort = _select_cohort(conn)
    finally:
        conn.close()

    if limit is not None:
        cohort = cohort[:limit]

    log(f"cohort: {len(cohort)} rows eligible")
    if dry_run:
        # Estimate: median priced call ~ $0.001 × 3 runs per model
        est_cost = len(cohort) * 3 * 0.001
        log(f"would bench {len(cohort)} models (dry-run), est. cost ${est_cost:.2f}")
        return 0

    running_cost = 0.0
    models_updated = 0
    models_failed = 0
    started_at = datetime.now(UTC).isoformat()

    for i, row in enumerate(cohort, 1):
        agent_id = row["id"]
        if running_cost >= cost_cap_usd:
            log(f"cost_stop: ${running_cost:.4f} >= cap ${cost_cap_usd} after {i - 1} calls")
            break
        log(f"[{i}/{len(cohort)}] bench {agent_id} (running cost ${running_cost:.4f})")
        result = bench_median(agent_id, api_key)
        running_cost += result["cost_usd"]
        if result["error"]:
            models_failed += 1
            log(f"  → FAIL: {result['error']}")
            continue
        if _write_result(db_path, agent_id, result):
            models_updated += 1
            log(f"  → tps={result['tps']} ttft={result['ttft_ms']}ms cost=${result['cost_usd']}")
        else:
            models_failed += 1
        time.sleep(RATE_LIMIT_SLEEP_S)

    _append_log(
        {
            "run_at": started_at,
            "finished_at": datetime.now(UTC).isoformat(),
            "cohort_size": len(cohort),
            "models_updated": models_updated,
            "models_failed": models_failed,
            "total_cost_usd": round(running_cost, 6),
            "cost_cap_usd": cost_cap_usd,
            "cost_stop": running_cost >= cost_cap_usd,
        }
    )
    log(
        f"summary: cohort={len(cohort)} updated={models_updated} "
        f"failed={models_failed} cost=${running_cost:.4f}"
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="OR microbench for output_tokens_per_sec + ttft_ms")
    p.add_argument("--dry-run", action="store_true", help="Show cohort + est cost only")
    p.add_argument("--limit", type=int, default=None, help="Cap models per run (smoke test)")
    p.add_argument(
        "--cost-cap", type=float, default=COST_CAP_USD, help=f"USD cap (default: {COST_CAP_USD})"
    )
    p.add_argument("--db", type=Path, default=DB_PATH)
    args = p.parse_args()
    return run_microbench(args.db, args.cost_cap, args.dry_run, args.limit)


if __name__ == "__main__":
    sys.exit(main())
