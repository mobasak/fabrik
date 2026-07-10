"""openrouter_complete — HumanEval+/MBPP+ completion generator on the vendored subagents transport.

Drop-in replacement for evalplus's `openai.OpenAI(base_url=OR)` completion step, which mis-parses
OpenRouter's streaming SSE (the `json.decoder.JSONDecodeError`). This calls `libs.subagents._transport.run`
instead — the SAME primitive every pool agent uses to talk to OpenRouter, so it is proven OR-compatible
(streaming, provider reroute on content-stall, retry, cost accounting). The eval step (sandboxed
execution + pass@1) stays evalplus's and runs offline against the produced samples `.jsonl`.
"""
# AFTER-EDIT: none

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from libs.subagents._client import OpenRouterClient
from libs.subagents._transport import Liveness, Result, run

# Greedy + deterministic — matches evalplus's default `temp_0.0` protocol. Fresh copy per call (see _run).
_BODY = {"temperature": 0.0, "max_tokens": 2048}

# 3-min hard ceiling + 60s first-token deadline so a stalling provider fails fast into a reroute.
# restart_max stays at the Liveness default 2 (the transport owns retry/reroute).
_LIVENESS = Liveness(hard_timeout_s=180.0, first_token_timeout_s=60.0)


def _run(model: str, prompt: str, *, client: OpenRouterClient, max_cost_usd: float) -> Result:
    """One greedy OR call → the full Result. `body={**_BODY}` is a fresh per-call copy (thread-safe)."""
    return run(
        model,
        [{"role": "user", "content": prompt}],
        body={**_BODY},
        liveness=_LIVENESS,
        client=client,
        max_cost_usd=max_cost_usd,
    )


def complete(
    model: str, prompt: str, *, client: OpenRouterClient, max_cost_usd: float = 0.50
) -> str:
    """One greedy completion. Returns '' if the provider streamed nothing (zero-token stall)."""
    return _run(model, prompt, client=client, max_cost_usd=max_cost_usd).text or ""


def generate_samples(
    model: str,
    problems: dict[str, str],  # task_id -> the prompt evalplus assembled
    out_path: str | Path,
    *,
    max_concurrency: int = 8,
    solution_key: str = "solution",  # evalplus>=0.2 field; older raw format uses "completion" — confirm
    env_path: str | None = ".env",
) -> tuple[Path, float]:
    """Generate one greedy completion per problem, write evalplus's samples `.jsonl` in problems order,
    and return `(path, total_cost_usd)`. A per-problem failure writes an empty solution AND logs to
    stderr (a SYSTEMATIC break is visible as `[error]` lines, not silently scored 0). A
    `finish_reason="length"` truncation is logged too (it fails eval — surface it)."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    client = _resolve_client(env_path=env_path)

    def _one(item: tuple[str, str]) -> tuple[dict, float]:
        task_id, prompt = item
        try:
            r = _run(model, prompt, client=client, max_cost_usd=0.50)
            if r.finish_reason == "length":
                print(
                    f"[warn] {task_id}: hit max_tokens (truncated) — may falsely fail",
                    file=sys.stderr,
                )
            return {"task_id": task_id, solution_key: r.text or ""}, (r.cost_usd or 0.0)
        except Exception as exc:  # noqa: BLE001 — one bad problem never aborts the batch, but MAKE IT VISIBLE
            print(
                f"[error] {task_id}: completion FAILED ({type(exc).__name__}: {exc}) — empty solution",
                file=sys.stderr,
            )
            return {"task_id": task_id, solution_key: ""}, 0.0

    with ThreadPoolExecutor(max_workers=max_concurrency) as ex:
        results = list(
            ex.map(_one, problems.items())
        )  # map preserves input order → deterministic jsonl

    total_cost = sum(cost for _, cost in results)
    with out.open("w", encoding="utf-8") as fh:
        for row, _ in results:
            fh.write(json.dumps(row) + "\n")
    return out, total_cost


def _resolve_client(*, env_path: str | None = ".env") -> OpenRouterClient:
    """Build an OpenRouterClient from OPENROUTER_API_KEY (mirrors _transport._resolve_client)."""
    import os

    if env_path and not os.getenv("OPENROUTER_API_KEY"):
        try:
            from libs.subagents._dotenv import load_env

            load_env(env_path)
        except Exception:  # noqa: BLE001 — best-effort; a clear error below if the key is still absent
            pass
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            f"OPENROUTER_API_KEY not set and not found in {env_path!r} — put it in your project's "
            ".env (the curated subagents key) or export it before running the bench."
        )
    return OpenRouterClient(
        api_key,
        referer=os.getenv("SUBAGENTS_REFERER"),
        title=os.getenv("SUBAGENTS_TITLE") or "coding-microbench",
    )
