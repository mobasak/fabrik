"""Phase C — methodology.py: distilled /fabrik-* prompt presets."""

from __future__ import annotations

import pytest

from subagents.methodology import METHODOLOGY_KINDS, methodology


def test_every_kind_returns_a_nonempty_prompt() -> None:
    for kind in METHODOLOGY_KINDS:
        text = methodology(kind)  # type: ignore[arg-type]
        assert isinstance(text, str) and len(text.strip()) > 20


def test_presets_are_distinct() -> None:
    assert methodology("review") != methodology("code")
    assert methodology("research") != methodology("docs")


def test_unknown_kind_raises_value_error() -> None:
    with pytest.raises(ValueError, match="unknown methodology"):
        methodology("nonsense")  # type: ignore[arg-type]


def test_exported_from_package() -> None:
    import subagents

    assert subagents.methodology("code") == methodology("code")
