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
    assert time.time() - floor <= hook._SIXTH_CAUSE_MAX_EDIT_AGE_S + 5


def test_a_real_baseline_is_used_verbatim() -> None:
    """...and the fallback must not override a baseline that EXISTS, or the bound has replaced
    the measurement it was only meant to stand in for."""
    baseline = time.time() - 3600.0
    assert hook._sixth_cause_floor(baseline) == baseline


def test_the_floor_never_drops_below_the_ledgers_birth() -> None:
    """Pre-ledger edits were adjudicated by the per-session rule of their day and no ledger holds
    their closes — re-judging them can only re-block."""
    # the INVARIANT, not the old exact value: with the age bound in place the answer for an
    # ancient baseline is `now - the window`, which is itself well above the ledger's birth.
    ancient = hook._LEDGER_EPOCH - 1_000_000.0
    assert hook._sixth_cause_floor(ancient) >= hook._LEDGER_EPOCH
    # and a ledger-epoch-era edit is dropped either way, which is what the rule is FOR
    assert (
        hook._this_sessions_edits(
            {"scripts/old.py": hook._LEDGER_EPOCH - 10}, hook._sixth_cause_floor(ancient)
        )
        == {}
    )


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


def test_the_named_files_clause_is_exercised_not_mirrored() -> None:
    """⚠️ THIS USED TO BE A MIRROR, and the mirror drifted from the hook it copied.

    Round 1 wrote a `_render_block` helper that re-implemented the message expression, pinned by
    four substrings. Executed in round 2: changing the real `", ".join` to `"; "` left the mirror
    AND its pin green while the rendered block changed — a second implementation and a pin too
    coarse to notice. The clause now lives in the hook as `_named_files_phrase`, and this calls
    the real thing, so there is nothing to drift.
    """
    names = [f"{c}.py" for c in "abcdefghij"]
    assert hook._named_files_phrase([]) == ""
    assert hook._named_files_phrase(names[:1]) == "Named: a.py. "
    assert hook._named_files_phrase(names[:3]) == "Named: a.py, b.py, c.py. ", (
        "3 is not a truncation"
    )
    assert hook._named_files_phrase(names[:4]) == "Named: a.py, b.py, c.py (+1 more). "
    assert hook._named_files_phrase(names) == "Named: a.py, b.py, c.py (+7 more). "


def test_the_block_calls_the_clause_rather_than_rebuilding_it() -> None:
    """The extraction is only worth having if the message actually uses it."""
    src = _HOOK.read_text(encoding="utf-8")
    block = src.split("UNREVIEWED SPONTANEOUS WORK")[1][:1400]
    assert "_named_files_phrase(_unreviewed_files)" in block, "the block rebuilds the clause"
    assert '", ".join' not in block, "a second join in the message means the clause was re-inlined"


def test_the_edit_age_phrase_never_renders_a_lossy_window() -> None:
    """`int(seconds // 3600)` rendered `0h` for any sub-hour value and `1h` for 90 minutes — and
    the message is the only place the window is disclosed, so the lossy form would have started
    lying at exactly the moment someone tuned it down."""
    import contextlib

    original = hook._SIXTH_CAUSE_MAX_EDIT_AGE_S
    try:
        for seconds, expected in (
            (86400.0, "within the last 24h"),
            (5400.0, "within the last 1.5h"),
            (3599.0, "within the last 1.0h"),
            (1800.0, "within the last 0.5h"),
            (30.0, "within the last 30s"),
        ):
            hook._SIXTH_CAUSE_MAX_EDIT_AGE_S = seconds
            assert hook._edit_age_phrase() == expected, (seconds, hook._edit_age_phrase())
    finally:
        hook._SIXTH_CAUSE_MAX_EDIT_AGE_S = original
    with contextlib.suppress(AttributeError):
        assert original == hook._SIXTH_CAUSE_MAX_EDIT_AGE_S


def test_the_block_does_not_claim_a_window_it_exempts_files_from() -> None:
    """`ts == 0` (an unparseable transcript timestamp) is kept by `_this_sessions_edits` and
    COUNTED by `_unreviewed_code_file_names` — both say so in their docstrings — so a message
    reading "edited in the last 24h" was false for exactly those files. The agent opens one,
    finds a months-old committed edit, and learns to warn the block through."""
    src = _HOOK.read_text(encoding="utf-8")
    block = src.split("UNREVIEWED SPONTANEOUS WORK")[1][:900]
    assert "no readable timestamp" in block, "the block still claims a window it exempts files from"


def test_the_floor_is_one_max_not_a_branch() -> None:
    """Two implementations of one rule, and the stale one reads exactly like the current one —
    the defect `_unreviewed_code_file_names`'s own docstring names, applied to its neighbour."""
    # ⚠️ AST, not a substring count. The first cut did `body.count("max(") == 1` and the
    # DOCSTRING says "ONE `max()`" — so the grader counted its own prose and read 2. A structural
    # question deserves a structural answer.
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(hook._sixth_cause_floor)))
    fn = tree.body[0]
    branches = [n for n in ast.walk(fn) if isinstance(n, (ast.If, ast.IfExp))]
    maxes = [
        n
        for n in ast.walk(fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "max"
    ]
    assert not branches, f"the branch survived alongside the max(): {len(branches)} branch node(s)"
    assert len(maxes) == 1, f"{len(maxes)} max() calls — the rule must live in exactly one place"
    assert len(maxes[0].args) == 3, "the three bounds are baseline, the age window, the ledger"
