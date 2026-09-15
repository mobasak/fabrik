"""T5.4 (01M25Y93RB): the sixth cause's floor is BOUNDED, and its block NAMES files.

Reproduced on the hub 2026-09-12: a session whose transcript spanned 5.7 days reported 20 code
files last edited 2026-06-04…06-16 as uncovered, while a `/fabrik-plan-review` record with 55
covered windows was live. Two defects in one block — the floor disarmed entirely when the
SessionStart baseline could not be stat'd, and the message named neither a count nor a file, so
the reader had no way to check the claim or act on it.
"""

from __future__ import annotations

import importlib.util
import time
from pathlib import Path

_HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "final_gate_stop.py"
_spec = importlib.util.spec_from_file_location("fgs_sixth", _HOOK)
hook = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(hook)

_JUNE = 1780000000.0  # well before any plausible session, well after the ledger's birth


def test_a_missing_baseline_still_has_a_floor() -> None:
    """THE DEFECT. `session_floor == 0.0` meant "keep everything back to the ledger's birth",
    which on a resumed transcript is months. It is now a bounded window ending now."""
    floor = hook._sixth_cause_floor(0.0)
    assert floor > _JUNE, "the June edits would still be inside the floor"
    assert floor <= time.time(), "the floor cannot be in the future"
    assert time.time() - floor <= hook._RESUMED_TRANSCRIPT_FALLBACK_S + 5


def test_a_real_baseline_is_used_verbatim() -> None:
    """...and the fallback must not override a baseline that EXISTS, or the bound has replaced
    the measurement it was only meant to stand in for."""
    baseline = time.time() - 3600.0
    assert hook._sixth_cause_floor(baseline) == baseline


def test_the_floor_never_drops_below_the_ledgers_birth() -> None:
    """Pre-ledger edits were adjudicated by the per-session rule of their day and no ledger holds
    their closes — re-judging them can only re-block."""
    ancient = hook._LEDGER_EPOCH - 1_000_000.0
    assert hook._sixth_cause_floor(ancient) == hook._LEDGER_EPOCH


def test_a_resumed_transcripts_ancient_edits_are_not_this_sessions_work() -> None:
    """End to end through the filter the cause actually uses, with no baseline available."""
    authored = {
        "scripts/june_one.py": _JUNE,
        "scripts/june_two.py": _JUNE + 600,
        "scripts/today.py": time.time() - 60,
    }
    kept = hook._this_sessions_edits(authored, hook._sixth_cause_floor(0.0))
    assert set(kept) == {"scripts/today.py"}, kept


def test_the_count_is_the_length_of_the_names() -> None:
    """One traversal, two readers. A count computed separately from the list it describes is two
    implementations of one rule, and the stale one reads exactly like the current one."""
    authored = {
        "scripts/a.py": 100.0,
        "scripts/b.py": 200.0,
        "docs/c.md": 300.0,  # not a code extension
        "scripts/d.py": 0,  # unknown timestamp COUNTS — unknown is not covered
    }
    windows = [(150.0, 250.0)]
    names = hook._unreviewed_code_file_names(authored, windows)
    assert names == ["scripts/a.py", "scripts/d.py"], names
    assert hook._unreviewed_code_files(authored, windows) == len(names)


def test_the_names_are_sorted_so_the_block_is_stable() -> None:
    """A block that names three DIFFERENT files on each attempt reads as three problems."""
    authored = {f"scripts/{c}.py": 100.0 for c in "zyxw"}
    assert hook._unreviewed_code_file_names(authored, [(500.0, 600.0)]) == [
        "scripts/w.py",
        "scripts/x.py",
        "scripts/y.py",
        "scripts/z.py",
    ]


def test_the_block_text_names_files_and_a_count() -> None:
    """Graded on the producer: the message has to interpolate both, or the reader is back to an
    assertion they cannot check."""
    src = _HOOK.read_text(encoding="utf-8")
    block = src.split("UNREVIEWED SPONTANEOUS WORK")[1][:1200]
    assert "{_unreviewed} code file(s)" in block, "the block states no count"
    assert "_unreviewed_files[:3]" in block, "the block names no file"
    assert "more)" in block, "a truncated list must say how many it truncated"
