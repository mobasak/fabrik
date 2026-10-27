"""A ``.env`` KEY is validated (W-aa69894d): a key outside compose's name grammar would inject or
corrupt ``.env`` lines, so ``format_env_line`` refuses it before returning any text."""

from __future__ import annotations

import pytest

from fabrik.env_file import format_env, format_env_line


@pytest.mark.parametrize("key", ["A B", "A=B", "A\nB", "A#B", "1A", "", "A\x00"])
def test_a_key_outside_the_grammar_is_refused(key: str) -> None:
    with pytest.raises(ValueError):
        format_env_line(key, "v")


@pytest.mark.parametrize("key", ["A", "_A1", "A.B", "A-B", "DATABASE_URL"])
def test_a_key_inside_the_grammar_is_written(key: str) -> None:
    assert format_env_line(key, "v") == f"{key}=v"


def test_a_refused_key_names_itself_by_repr_and_writes_nothing() -> None:
    written: list[str] = []
    with pytest.raises(ValueError, match=r"'A\\nB'"):
        written.append(format_env_line("A\nB", "INJECTED=1"))
    assert written == []
    with pytest.raises(ValueError):
        format_env({"OK": "1", "A B": "2"})
