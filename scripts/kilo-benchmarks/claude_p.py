# AFTER-EDIT: none (single-shot claude -p dispatch shim; consumed by microbench_review.py + microbench_coding_direct.py)
"""Single-shot `claude -p` dispatch shim for benchmark scoring (VENDOR + ENHANCE claude-evaluator).

Mirrors claude-evaluator._call_cli's subprocess (npx @anthropic-ai/claude-code --print --model
--system-prompt, prompt via stdin, fail-closed) but with **--output-format json** to capture the `usage`
token block _call_cli discards under --output-format text. Single-shot, NO --allowedTools, NO --add-dir,
single turn — transport parity with the OpenRouter single completion. The methodology rides in `prompt`
(the user content), NOT --system-prompt, so `system` defaults empty and the flag is omitted when empty.

Grounded 2026-07-20 (CLI 2.1.216): `--output-format json` returns top-level {result, usage, ...}; usage keys
are snake_case input_tokens/output_tokens/cache_read_input_tokens/cache_creation_input_tokens.
"""
from __future__ import annotations

import json
import subprocess

# claude-code/<tier> -> the live model id (grounded on-disk byModel keys + `claude --help`).
ALIASES = {
    "claude-code/opus": "claude-opus-4-8",
    "claude-code/sonnet": "claude-sonnet-5",
    "claude-code/haiku": "claude-haiku-4-5-20251001",
    "claude-code/fable": "claude-fable-5",
}

_USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


def claude_p_call(
    model: str, prompt: str, *, system: str = "", timeout: float = 150.0
) -> tuple[str, dict]:
    """Run one single-shot `claude -p` completion. Returns ``(text, usage)``.

    ``model`` is a ``claude-code/<tier>`` id; ``prompt`` is the full user content (the methodology rides
    here, NOT ``--system-prompt``, for transport parity with the OpenRouter user-only call). ``system`` is
    empty by default and the flag is omitted when empty (no system prompt). Raises ``RuntimeError`` on a
    non-zero exit or unparseable json — fail-closed, never a silent empty ``usage``.
    """
    if model not in ALIASES:
        raise KeyError(f"unknown claude-code model {model!r}")
    cmd = [
        "npx",
        "@anthropic-ai/claude-code",
        "--print",
        "--output-format",
        "json",
        "--model",
        ALIASES[model],
    ]
    if system:
        cmd += ["--system-prompt", system]
    proc = subprocess.run(  # noqa: S603 — fixed argv, no shell; prompt via stdin
        cmd, input=prompt, capture_output=True, text=True, timeout=timeout
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude-code CLI exited {proc.returncode}: {(proc.stderr or '').strip()[:500]}"
        )
    try:
        data = json.loads(proc.stdout)
    except (ValueError, TypeError) as e:
        raise RuntimeError(
            f"claude-code CLI json parse failed: {e}; out={proc.stdout[:200]!r}"
        ) from e
    if not isinstance(data, dict):
        raise RuntimeError(f"claude-code CLI returned non-object json: {proc.stdout[:200]!r}")
    # In-band error (exit 0 but is_error) — max-turns / API error surfaced in the payload, not the exit code.
    if data.get("is_error"):
        raise RuntimeError(
            f"claude-code CLI reported is_error (subtype={data.get('subtype')!r}, "
            f"api_error_status={data.get('api_error_status')!r})"
        )
    text = data.get("result") or ""
    raw = data.get("usage") or {}
    usage = {k: int(raw.get(k, 0) or 0) for k in _USAGE_KEYS}
    # Fail-closed: a valid-but-usage-less response (missing usage, or zero output = no completion) must NOT
    # sail through as a $0 run — that would bias the ranking axis toward claude-p. Raise so the caller's
    # dispatch branch records it as an error, exactly like a failed OpenRouter call.
    if not raw or usage["output_tokens"] <= 0:
        raise RuntimeError(
            f"claude-code CLI returned no usable completion (empty/zero usage): {proc.stdout[:200]!r}"
        )
    return text, usage
