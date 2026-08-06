# AFTER-EDIT: scripts/enforcement/check_retired_terms.py
"""Behavior contract for the retired-tech tripwire (docs-truth plan Phase F).

The load-bearing behavior: this check NEVER blocks — WARN lines to stdout, exit 0
always (final_gate fails on any non-zero exit regardless of the advisory flag, so
WARN-only semantics live in the exit code).
"""

import subprocess
import sys
from pathlib import Path

REPO = Path("/opt/fabrik")
SCRIPT = REPO / "scripts/enforcement/check_retired_terms.py"
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))

import check_retired_terms as crt  # noqa: E402


def test_always_exits_zero_even_with_warns():
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False)
    assert r.returncode == 0
    assert "check_retired_terms:" in r.stdout  # OK line or WARN summary


def test_marked_mention_is_silent_unmarked_warns():
    assert crt.TERMS.search("we still call Kilo CLI here")
    assert crt.MARKERS.search("Kilo CLI (retired 2026-07-19)")
    assert not crt.MARKERS.search("dispatch via Kilo CLI for speed")


def test_archive_and_ledger_sources_excluded():
    assert "docs/archive/" in crt.SKIP_PREFIXES
    assert "docs/LESSONS_LEARNT.md" in crt.SKIP_EXACT
