"""Spontaneous code changes owe a review — and the hook now knows what "spontaneous" means.

Operator, 2026-08-29: work done in plain chat (no /fabrik-* command) changes the repo and nothing
triggers a review; typing /fabrik-review is heavy and gets forgotten. The mechanical insight: every
command opens a run record (corpus predicate 5, gate-enforced), so a session that authored CODE
with NO run record at all IS spontaneous work by construction. Commanded work exempts itself.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "final_gate_stop", REPO / ".claude" / "hooks" / "final_gate_stop.py"
)
fgs = importlib.util.module_from_spec(_spec)
sys.modules["final_gate_stop"] = fgs
_spec.loader.exec_module(fgs)


def test_code_edits_with_no_record_block_up_to_the_cap():
    a = 0
    for expect in (1, 2, 3):
        action, a = fgs.decide_review(code_files=3, has_any_record=False, attempts=a)
        assert action == "block_review" and a == expect
    action, a = fgs.decide_review(code_files=3, has_any_record=False, attempts=a)
    assert action == "allow_warn_review", "cap must warn through, never trap (anti-trap law)"


def test_any_run_record_exempts_commanded_work():
    """An /fabrik-execute-plan turn commits code under ITS record; its own contract owns the
    review discipline. The checkpoint belongs to record-less work only."""
    action, a = fgs.decide_review(code_files=9, has_any_record=True, attempts=2)
    assert action == "allow" and a == 0, "a record must exempt AND reset the counter"


def test_doc_only_sessions_never_fire():
    action, a = fgs.decide_review(code_files=0, has_any_record=False, attempts=2)
    assert action == "allow" and a == 0


def test_code_file_classifier():
    files = {"scripts/x.py": 3, "docs/A.md": 9, "CHANGELOG.md": 2, ".claude/settings.json": 1,
             "a/b.ts": 1, "notes.txt": 5}
    assert fgs._count_code_files(files) == 3, "py + json + ts are code; md/txt are not"


def test_counters_extend_compatibly():
    """Old 5-slot counter files must read as 0 for the new slot — a synced hook meeting a
    pre-upgrade counter file must not crash or misattribute attempts."""
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("1,2,3,4,5")
        p = Path(f.name)
    vals = fgs._read_counters(p)
    assert vals == (1, 2, 3, 4, 5, 0), vals
    p.unlink()


# --- the checkpoint is PER CHANGE, not per session (operator, 2026-09-06) ------------------------
# `_run_record_exists` answered "did this session EVER open a record?" — a per-session boolean.
# Measured: a session ran /fabrik-review-scoped at 01:45, then made TEN plain-chat commits across
# the day, and never tripped the sixth cause because that one morning record exempted everything
# after it. The hook must ask "is there authored CODE newer than the last closed command?" — a
# closed command covers the edits made before its close and nothing after; a RUNNING record is
# the fifth cause's business and must not double-block here.

T = 1_800_000_000


def test_code_authored_after_the_last_closed_command_is_unreviewed():
    authored = {"src/a.py": T + 60, "src/b.py": T - 60, "docs/x.md": T + 600}
    horizon = fgs._review_horizon({"command": "fabrik-review-scoped", "state": "done", "updated_ts": T})
    assert horizon == T
    assert fgs._unreviewed_code_files(authored, horizon) == 1, "only a.py is newer than the close"


def test_no_record_at_all_leaves_every_code_file_unreviewed():
    authored = {"src/a.py": T, "src/b.py": T - 9999}
    assert fgs._review_horizon(None) is None
    assert fgs._unreviewed_code_files(authored, None) == 2


def test_a_running_record_is_the_fifth_causes_business_not_this_ones():
    authored = {"src/a.py": T + 60}
    horizon = fgs._review_horizon({"command": "fabrik-execute-plan", "state": "running", "updated_ts": T})
    assert fgs._unreviewed_code_files(authored, horizon) == 0, "never double-block a live command"


def test_a_blocked_close_covers_like_a_done_close():
    horizon = fgs._review_horizon({"command": "fabrik-review", "state": "blocked", "updated_ts": T})
    assert horizon == T


def test_malformed_record_reads_as_no_record():
    for rec in ({"state": "done"}, {"updated_ts": "soon", "state": "done"}, "junk", 42):
        assert fgs._review_horizon(rec) is None
