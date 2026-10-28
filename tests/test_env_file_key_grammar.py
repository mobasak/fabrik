"""A ``.env`` KEY is validated (W-aa69894d): a key outside compose's name grammar would inject or
corrupt ``.env`` lines, so ``format_env_line`` refuses it before returning any text."""

from __future__ import annotations

import pytest

from fabrik.env_file import format_env, format_env_line, parse_env


@pytest.mark.parametrize("key", ["A B", "A=B", "A\nB", "A#B", "1A", "", "A\x00"])
def test_a_key_outside_the_grammar_is_refused(key: str) -> None:
    with pytest.raises(ValueError):
        format_env_line(key, "v")


@pytest.mark.parametrize("key", ["A", "_A1", "A.B", "A-B", "DATABASE_URL"])
def test_a_key_inside_the_grammar_is_written(key: str) -> None:
    assert format_env_line(key, "v") == f"{key}=v"


def test_a_refused_key_writes_nothing() -> None:
    # A raise returns no line, and one bad key refuses the whole file.
    with pytest.raises(ValueError, match="not a valid variable name"):
        format_env_line("A\nB", "INJECTED=1")
    with pytest.raises(ValueError):
        format_env({"OK": "1", "A B": "2"})


def test_a_secret_bearing_key_from_a_broken_line_is_never_printed() -> None:
    # A broken VPS line parses as key = everything before its first `=`; written back, it is refused
    # without echoing the password the key holds.
    key = next(iter(parse_env("postgres://u:hunter2@h/db?x=y\n")))
    with pytest.raises(ValueError) as exc:
        format_env({key: "y"})
    assert "hunter2" not in str(exc.value)
    assert "a malformed key" in str(exc.value)
