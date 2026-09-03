"""Regression guard: the LiveCodeBench HF dataset cache must not live inside the hub tree.

2026-09-03: an 8.3 GB ``scripts/kilo-benchmarks/.lcb-hf-cache`` sat gitignored in the tree after
its setter left with the catalog engine (73bde59a). Every full-tree copy a session made for a
revert test or review sandbox dragged it along (28 GB in one session's scratchpad). The cache now
lives at ``${XDG_CACHE_HOME:-~/.cache}/fabrik/lcb-hf-cache``; the engine's ``HF_HOME`` default in
``/opt/ai-model-catalog/engine/`` is the only sanctioned writer.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ORPHAN = REPO / "scripts" / "kilo-benchmarks" / ".lcb-hf-cache"


def test_lcb_hf_cache_is_not_inside_the_tree() -> None:
    assert not ORPHAN.exists(), (
        f"{ORPHAN} is back inside the hub tree — every tree copy will drag it. "
        "Move it to ${XDG_CACHE_HOME:-~/.cache}/fabrik/lcb-hf-cache and point HF_HOME there."
    )
