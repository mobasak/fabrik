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


def _render_block(files: list[str]) -> str:
    """The block's message, built exactly as `main` builds it — the ONE expression under test.

    ⚠️ Kept in lockstep with `final_gate_stop.py` by `test_the_rendered_block_matches_the_hook`
    below, which asserts the hook's own source still contains the pieces this mirrors. A mirror
    nothing pins is a second implementation that drifts."""
    n = len(files)
    named = (
        "Named: " + ", ".join(files[:3]) + (f" (+{n - 3} more)" if n > 3 else "") + ". "
        if files
        else ""
    )
    return f"session authored {n} code file(s) ... {named}Run "


def test_the_truncation_arithmetic_is_executed_not_just_present() -> None:
    """⚠️ THE FIRST CUT OF THIS GRADER COULD NOT FAIL. It asserted the literal `_unreviewed - 3`
    appears in the source — so mutating it to `_unreviewed - 99` left 163 tests green (Phase F
    review, seat finding 1). The count is now EXERCISED at each boundary."""
    assert "Named: " not in _render_block([])
    assert _render_block(["a.py"]).count("Named: a.py. ") == 1
    assert "more)" not in _render_block(["a.py", "b.py", "c.py"]), "3 files is not a truncation"
    four = _render_block(["a.py", "b.py", "c.py", "d.py"])
    assert "Named: a.py, b.py, c.py (+1 more). " in four, four
    ten = _render_block([f"{c}.py" for c in "abcdefghij"])
    assert "(+7 more)" in ten, ten
    assert ten.count(".py") == 3 + 0, "only three names are listed"


def test_the_rendered_block_matches_the_hook() -> None:
    """The mirror above is only worth having if it is pinned to the real expression."""
    src = _HOOK.read_text(encoding="utf-8")
    block = src.split("UNREVIEWED SPONTANEOUS WORK")[1][:1400]
    assert "{_unreviewed} code file(s)" in block, "the block states no count"
    assert "_unreviewed_files[:3]" in block, "the block names no file"
    assert "_unreviewed - 3" in block, "the truncation count is not len-minus-three"
    assert "if _unreviewed > 3" in block, "the truncation has no boundary guard"


def test_the_age_bound_binds_even_with_a_real_baseline(tmp_path=None) -> None:
    """⚠️ THE CORRECTION THE PHASE F REVIEW FORCED. The first cut applied the bound only when the
    baseline was MISSING — and the shape 01M25Y93RB reports is a RESUMED transcript, which HAS a
    baseline; it is merely old. Measured live while this fired on the author's own session: the
    baseline was 135.3h old, so a 2.5-day-old entry for a file committed and reviewed to `done`
    was reported as unreviewed, and 87 of the 97 baselines on the box were older than the window."""
    ancient = time.time() - 135 * 3600
    floor = hook._sixth_cause_floor(ancient)
    assert floor > ancient, "an ancient baseline was used verbatim — the bound did not bind"
    assert time.time() - floor <= hook._SIXTH_CAUSE_MAX_EDIT_AGE_S + 5

    # a 2.5-day-old edit — the live false positive — is dropped
    assert hook._this_sessions_edits({"scripts/x.py": time.time() - 2.5 * 86400}, floor) == {}


def test_a_fresh_baseline_still_wins_over_the_age_bound() -> None:
    """...or the bound has replaced the measurement instead of bounding it. A session that started
    two hours ago must judge exactly its own two hours, not a day."""
    fresh = time.time() - 7200
    assert hook._sixth_cause_floor(fresh) == fresh


def test_the_block_names_the_window_because_the_floor_slides() -> None:
    """The floor moves between stops, so the same stop run twice can give different verdicts. A
    verdict that changes on its own, silently, is indistinguishable from a broken one — which is
    the complaint T5.4's file-naming half exists to answer, and it applies to the window too."""
    src = _HOOK.read_text(encoding="utf-8")
    block = src.split("UNREVIEWED SPONTANEOUS WORK")[1][:900]
    assert "_SIXTH_CAUSE_MAX_EDIT_AGE_S // 3600" in block, "the block does not name its window"


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
