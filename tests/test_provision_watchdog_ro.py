"""Highest-risk path for provision_watchdog_ro: the db-name injection guard.

`grant`/`revoke` interpolate the db name into GRANT/`\\c` SQL run as the postgres
superuser, so `_validate_db_name` is the security boundary — it must accept real
fabrik db ids (lowercase snake_case) and reject anything with quotes, spaces,
semicolons, dashes, or that's over-long / wrong-cased.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import provision_watchdog_ro as p  # noqa: E402


def test_validate_db_name_accepts_real_fabrik_ids():
    for ok in ["calendar_engine", "fabrik_claim_validator", "verify", "a", "db_1", "_x"]:
        assert p._validate_db_name(ok) == ok


@pytest.mark.parametrize(
    "bad",
    [
        'x"; DROP DATABASE y; --',  # classic injection
        "a; SELECT 1",              # statement break
        "a b",                      # space
        "calendar-engine",          # dash (kebab, not snake)
        "'quoted'",                 # quotes
        "",                         # empty
        "Uppercase",                # wrong case
        "1leading",                 # leading digit
        "a" * 64,                   # over 63 chars
        "public;",                  # trailing semicolon
    ],
)
def test_validate_db_name_rejects_unsafe(bad):
    with pytest.raises(ValueError):
        p._validate_db_name(bad)
