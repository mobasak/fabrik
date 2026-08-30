"""Curated NVIDIA Build tool-caller allowlist (from a live empirical eval, 2026-08-26).

Only these models reliably support OpenAI function/tool calling on NVIDIA Build. A
``tools_enabled=True`` unit on any OTHER NVIDIA model would have its tool schemas silently
ignored (the model just emits text and never calls a tool), so the dispatch REFUSES that
combination up front rather than run an inert tool-loop. A non-tool NVIDIA model is still
valid as a single-shot (``tools_enabled=False``) finder / reviewer / grader.

`pick_models` stays OpenRouter-ranked; NVIDIA ids never enter its table. A NVIDIA unit is
chosen by an EXPLICIT ``model=`` + ``provider="nvidia"`` — this allowlist only gates whether
that explicit choice may enable tools.
"""

from __future__ import annotations

__all__ = [
    "NVIDIA_TOOL_CALLERS",
    "DEFAULT_NVIDIA_TOOL_MODEL",
    "nvidia_supports_tools",
]

# Verified tool-callers (eval 2026-08-26: `tool=YES` on /chat/completions with a function schema).
NVIDIA_TOOL_CALLERS: frozenset[str] = frozenset(
    {
        "nvidia/nemotron-3-super-120b-a12b",  # DEFAULT — ~57 tok/s, reliable tool-caller
        "nvidia/nemotron-3-nano-30b-a3b",  # fastest (~56 tok/s), tool-capable
        "nvidia/nemotron-3-ultra-550b-a55b",  # most capable (slow ~7 tok/s)
        "openai/gpt-oss-120b",  # fastest overall (~109 tok/s)
        "openai/gpt-oss-20b",
        "minimaxai/minimax-m3",
        "poolside/laguna-xs-2.1",
        "moonshotai/kimi-k3",
    }
)

# RECOMMENDED model for a NVIDIA tools_enabled unit — the best speed/capability/reliability
# balance from the eval. A convenience constant for callers to pass as `model=`, NOT an
# auto-applied default: `AgentSpec.model` is a required field, so an unset model is a construction
# error, never a silent fallback to this value.
DEFAULT_NVIDIA_TOOL_MODEL = "nvidia/nemotron-3-super-120b-a12b"


def nvidia_supports_tools(model: str) -> bool:
    """True iff ``model`` is a NVIDIA Build model verified to support OpenAI tool-calling."""
    return model in NVIDIA_TOOL_CALLERS
