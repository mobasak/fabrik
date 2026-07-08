"""Behavior Contract for scripts/kilo-benchmarks/blocked_writes.py.

Phase D of plan-4 (pipeline-health coverage closure). Persistent per-day
review queue for safety-blocked direct-vendor writes.
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_record_creates_file_and_row(tmp_path, monkeypatch):
    """B1: first blocked write on a day creates the MD with a table row."""
    import blocked_writes

    monkeypatch.setattr(blocked_writes, "_CACHE_DIR", tmp_path)

    today = _dt.date(2026, 7, 8)
    out = blocked_writes.record_blocked_write(
        "cartesia", "sonic-2", 233.33, 1000.00, "diff>50%", "raw text", today=today
    )
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "# Blocked direct-vendor writes — 2026-07-08" in text
    assert "cartesia" in text and "sonic-2" in text
    assert "$233.3300" in text and "$1000.0000" in text
    assert "diff>50%" in text


def test_record_idempotent_within_day(tmp_path, monkeypatch):
    """B2: same (vendor, id, prices) tuple twice on same day → 1 row, not 2."""
    import blocked_writes

    monkeypatch.setattr(blocked_writes, "_CACHE_DIR", tmp_path)

    today = _dt.date(2026, 7, 8)
    args = ("cartesia", "sonic-2", 233.33, 1000.00, "diff>50%", "raw")
    out = blocked_writes.record_blocked_write(*args, today=today)
    first = out.read_text(encoding="utf-8")
    blocked_writes.record_blocked_write(*args, today=today)
    second = out.read_text(encoding="utf-8")
    assert first == second, "idempotency broken — row was duplicated"
    # And exactly one data row (header pipe count discounts the schema row).
    data_rows = [ln for ln in second.splitlines() if ln.startswith("| cartesia |")]
    assert len(data_rows) == 1


def test_record_cross_day(tmp_path, monkeypatch):
    """B3: next day's block writes to a new file, not appended to yesterday."""
    import blocked_writes

    monkeypatch.setattr(blocked_writes, "_CACHE_DIR", tmp_path)

    args = ("cartesia", "sonic-2", 233.33, 1000.00, "diff>50%", "raw")
    out1 = blocked_writes.record_blocked_write(*args, today=_dt.date(2026, 7, 8))
    out2 = blocked_writes.record_blocked_write(*args, today=_dt.date(2026, 7, 9))
    assert out1 != out2
    assert out1.name == "2026-07-08.md"
    assert out2.name == "2026-07-09.md"


def test_pipe_and_whitespace_escaped_in_raw(tmp_path, monkeypatch):
    """Raw text with `|` and newlines must not break the markdown table."""
    import blocked_writes

    monkeypatch.setattr(blocked_writes, "_CACHE_DIR", tmp_path)

    out = blocked_writes.record_blocked_write(
        "vendor",
        "id",
        1.0,
        2.0,
        "reason",
        "line1 | with pipe\nnewline\ttab",
        today=_dt.date(2026, 7, 8),
    )
    text = out.read_text(encoding="utf-8")
    # Every data row must have exactly the header's column count of pipes.
    header = [ln for ln in text.splitlines() if ln.startswith("| vendor |")][0]
    n_pipes = header.count("|")
    for ln in text.splitlines():
        if ln.startswith("| vendor |"):
            assert ln.count("|") == n_pipes, f"pipe corruption in row: {ln!r}"
