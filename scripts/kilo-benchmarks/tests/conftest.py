# AFTER-EDIT: test_canary_grounding_column.py | none
"""Provision `TEST_DATABASE_URL` for this suite's real-DB tests.

The three query-behavior tests here are the ONLY behavioral proof of the generator's
aggregation SQL — a silent `skipif` turns "green" into "never ran" (the '3 passed, 3 skipped'
hole `check_plan_tickets.py:201` documents for a sibling suite). When the env var is unset,
fall back to the box-standard throwaway database IF it is actually reachable; otherwise the
tests still skip, but this file prints the reason LOUDLY so a green run never masquerades as
coverage. Create the throwaway once per box:
  sudo -u postgres psql -c "CREATE DATABASE canary_grounding_test"
  sudo -u postgres psql -d canary_grounding_test -c "GRANT ALL ON SCHEMA public TO $USER"
"""

from __future__ import annotations

import os
import sys as _sys
from pathlib import Path as _Path

_LIBS_FOR_ALERTING = (
    _Path(__file__).resolve().parents[3] / "libs"
)  # `import alerting` in this suite is libs/alerting — the vendored copy is gone (D-110/FD6)
if str(_LIBS_FOR_ALERTING) not in _sys.path:
    _sys.path.insert(0, str(_LIBS_FOR_ALERTING))

_FALLBACK = "postgresql:///canary_grounding_test"

if not os.getenv("TEST_DATABASE_URL"):
    try:
        import psycopg

        with psycopg.connect(_FALLBACK, connect_timeout=3):
            pass
        os.environ["TEST_DATABASE_URL"] = _FALLBACK
    except Exception as exc:  # loud skip, never a silent one
        print(
            f"[kilo-tests conftest] TEST_DATABASE_URL unset and fallback {_FALLBACK} "
            f"unreachable ({exc}) — the DB-backed query tests WILL SKIP (that is lost "
            f"coverage, not a pass); see this file's docstring to provision the throwaway."
        )
