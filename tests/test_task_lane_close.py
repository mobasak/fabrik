"""Graders for the close half of ``scripts/task_lane.py`` (plan T03a; spec D1 close column, D3, D4,
D7 and § Lifecycle).

One test per Behavior Contract row of the ticket, plus one per boundary (2x appetite vs 2x + 1
minute, 800 vs 801 lines, 7 vs 8 Behaviours). Pure: ``measure_close`` is fed name-status rows
``(status, path, old_path)`` exactly as ``command_run.py`` produces them with
``--name-status -M -C``; nothing here touches git or the environment.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _module():
    name = "task_lane"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "task_lane.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        del sys.modules[name]
        raise
    return mod


def _record(**over):
    tl = _module()
    base = {
        "stamped": True,
        "files": ["src/app.py"],
        "design_paths": ["src/app.py"],
        "amendments": [],
        "behaviours": 3,
        "appetite": 240,
        "started_at": 1_000_000.0,
        "consumers": "internal",
        "sync_hits": set(),
    }
    base.update(over)
    return tl.LaneRecord(**base)


def _never(_path: str) -> bool:
    return False


def _close(rec, commits, *, verb="done", minutes=10.0, loc_added=50, receipt=None, excluded=_never):
    return _module().measure_close(
        rec,
        commits,
        excluded=excluded,
        verb=verb,
        now=rec.started_at + minutes * 60,
        loc_added=loc_added,
        receipt=receipt,
    )


# ── V2: new-source, a copy counted as a new file ─────────────────────────────────────────


def test_three_new_sources_one_a_copy_upgrade_new_source_and_classify_agrees():
    rows = [
        ("A", "src/one.py", None),
        ("A", "src/two.py", None),
        ("C", "src/three.py", "src/one.py"),
    ]
    rec = _record(design_paths=["src/one.py", "src/two.py", "src/three.py"])
    v = _close(rec, [rows])
    assert "new-source" in v.upgrade
    assert v.needs_full_review is True
    assert v.refused is None
    assert (
        _module().classify_commit(rows, repo_kind="project", sync_regex="") == "chain: new-source"
    )


def test_new_source_counted_across_commits():
    rec = _record(design_paths=["src/one.py", "src/two.py", "src/three.py"])
    commits = [
        [("A", "src/one.py", None), ("A", "src/two.py", None)],
        [("A", "src/three.py", None)],
    ]
    v = _close(rec, commits)
    assert "new-source" in v.upgrade
    assert v.needs_full_review is True


def test_two_new_sources_is_not_an_upgrade():
    rec = _record(design_paths=["src/one.py", "src/two.py"])
    v = _close(rec, [[("A", "src/one.py", None), ("C", "src/two.py", "src/one.py")]])
    assert "new-source" not in v.upgrade
    assert v.needs_full_review is False


# ── V3: contract before any exclusion ────────────────────────────────────────────────────


def test_contract_path_hidden_by_excluded_still_upgrades_and_classify_agrees():
    rows = [("M", "src/app.py", None), ("M", "specs/services/x.yaml", None)]
    rec = _record(consumers="internal")

    def hides_spec(path: str) -> bool:
        return path.startswith("specs/")

    v = _close(rec, [rows], excluded=hides_spec)
    assert "contract" in v.upgrade
    assert v.needs_full_review is True
    assert _module().classify_commit(rows, repo_kind="project", sync_regex="") == "chain: contract"


def test_contract_on_the_old_path_of_a_rename():
    rec = _record(design_paths=["src/app.py", "specs/old.yaml"])
    v = _close(rec, [[("R", "specs/old.yaml", "specs/services/x.yaml")]])
    assert "contract" in v.upgrade


# ── V4: undeclared paths, amendments, verbs, the receipt ─────────────────────────────────

UNDECLARED = [("M", "src/app.py", None), ("M", "src/other.py", None)]


def test_undeclared_path_refuses_done_naming_it():
    v = _close(_record(), [UNDECLARED], verb="done")
    assert v.refused is not None
    assert "src/other.py" in v.refused
    assert "src/other.py" in v.oversized_mini


def test_design_amend_answers_the_refusal_and_is_counted():
    v = _close(_record(amendments=["src/other.py", "./src/other.py"]), [UNDECLARED], verb="done")
    assert v.refused is None
    assert v.design_amends == 1
    assert v.amended_paths == ["src/other.py"]
    assert v.oversized_mini == []


def test_blocked_and_handoff_record_never_refuse():
    for verb in ("blocked", "handoff"):
        v = _close(_record(), [UNDECLARED], verb=verb)
        assert v.refused is None, verb
        assert v.oversized_mini == ["src/other.py"], verb


def test_receipt_path_is_exempt_from_the_declaration_check():
    receipt = "docs/development/reviews/2026-10-02-x-review.md"
    rows = [("M", "src/app.py", None), ("A", receipt, None)]
    assert _close(_record(), [rows], receipt=receipt).refused is None
    refused = _close(_record(), [rows], receipt=None).refused
    assert refused is not None and receipt in refused


def test_excluded_paths_need_no_declaration():
    rows = [("M", "src/app.py", None), ("M", "CHANGELOG.md", None)]
    v = _close(_record(), [rows], excluded=lambda p: p == "CHANGELOG.md")
    assert v.refused is None
    assert v.oversized_mini == []


def test_stamped_record_with_no_design_is_refused():
    v = _close(_record(design_paths=[]), [[("M", "src/app.py", None)]])
    assert v.refused is not None and "src/app.py" in v.refused


def test_copy_of_a_declared_file_does_not_inherit_membership():
    v = _close(_record(), [[("C", "src/copy.py", "src/app.py")]])
    assert v.refused is not None and "src/copy.py" in v.refused


# ── V5: the Behaviours cap ───────────────────────────────────────────────────────────────


def test_eight_behaviours_upgrade():
    v = _close(_record(behaviours=8), [[("M", "src/app.py", None)]])
    assert "behaviours" in v.upgrade
    assert v.needs_full_review is False


def test_seven_behaviours_do_not_upgrade():
    v = _close(_record(behaviours=7), [[("M", "src/app.py", None)]])
    assert "behaviours" not in v.upgrade


# ── D3.2 / D7: multi-commit carry and the sync single commit ─────────────────────────────


def test_rename_in_first_commit_carries_membership_into_second():
    rec = _record(design_paths=["src/app.py"])
    commits = [[("R", "src/core.py", "src/app.py")], [("M", "src/core.py", None)]]
    v = _close(rec, commits)
    assert v.refused is None
    assert v.oversized_mini == []


def test_rename_old_path_is_judged_on_its_own_membership():
    rec = _record(design_paths=["src/new.py"])
    v = _close(rec, [[("R", "src/new.py", "src/legacy.py")]])
    assert v.refused is not None and "src/legacy.py" in v.refused
    assert v.oversized_mini == ["src/legacy.py"]


def test_without_the_carry_the_second_commit_edit_is_undeclared():
    rec = _record(design_paths=["src/app.py"])
    v = _close(rec, [[("M", "src/core.py", None)]])
    assert v.refused is not None and "src/core.py" in v.refused


def test_sync_path_run_with_two_commits_is_refused():
    rec = _record(sync_hits={"scripts/enforcement/x.py"}, design_paths=["src/app.py"])
    commits = [[("M", "src/app.py", None)], [("M", "src/app.py", None)]]
    v = _close(rec, commits, verb="done")
    assert v.refused is not None and "once" in v.refused
    assert _close(rec, commits[:1], verb="done").refused is None
    assert _close(_record(), commits, verb="done").refused is None


# ── V6 / D4: appetite, 2x vs 2x + 1 minute ───────────────────────────────────────────────


def test_past_twice_the_appetite_records_over_appetite_and_upgrade_line():
    v = _close(_record(appetite=60), [[("M", "src/app.py", None)]], minutes=121)
    assert v.over_appetite is True
    assert "appetite" in v.upgrade
    assert v.needs_full_review is False
    assert any(f.startswith("UPGRADE:") and "appetite" in f for f in v.findings)
    assert v.refused is None


def test_exactly_twice_the_appetite_is_not_over():
    v = _close(_record(appetite=60), [[("M", "src/app.py", None)]], minutes=120)
    assert v.over_appetite is False
    assert "appetite" not in v.upgrade
    assert not any("appetite" in f for f in v.findings)


# ── D3.4: loc_added, 800 vs 801 ──────────────────────────────────────────────────────────


def test_801_lines_record_and_emit_a_change_finding_never_refuse():
    v = _close(_record(), [[("M", "src/app.py", None)]], loc_added=801)
    assert v.loc_added == 801
    assert any(f.startswith("change:") and "801" in f for f in v.findings)
    assert v.refused is None


def test_800_lines_emit_no_finding():
    v = _close(_record(), [[("M", "src/app.py", None)]], loc_added=800)
    assert v.loc_added == 800
    assert not any(f.startswith("change:") for f in v.findings)


# ── § Lifecycle: an unstamped record keeps today's close ─────────────────────────────────


def test_unstamped_record_measures_last_commit_only_and_never_refuses():
    rec = _record(
        stamped=False,
        files=["src/app.py"],
        design_paths=["src/other.py"],
        amendments=["src/other.py"],
        behaviours=9,
        appetite=1,
    )
    commits = [
        [("A", "src/a.py", None), ("A", "src/b.py", None), ("A", "src/c.py", None)],
        [("M", "src/app.py", None), ("M", "src/other.py", None)],
    ]
    v = _close(rec, commits, verb="done", minutes=999, loc_added=5000)
    assert v.refused is None
    assert v.oversized_mini == ["src/other.py"]
    assert v.upgrade == []
    assert v.needs_full_review is False
    assert v.over_appetite is False


# ── round-1 fixes ────────────────────────────────────────────────────────────────────────


def test_rename_from_an_excluded_old_path_inherits_nothing():
    rec = _record(design_paths=["src/app.py"])
    rows = [("R100", "src/evil.py", ".fabrik/work/W-x.json")]
    v = _close(rec, [rows], excluded=lambda p: p.startswith(".fabrik/"))
    assert v.refused is not None and "src/evil.py" in v.refused
    assert v.oversized_mini == ["src/evil.py"]


def test_rename_from_the_receipt_inherits_nothing():
    receipt = "docs/development/reviews/r.md"
    v = _close(_record(), [[("R100", "src/evil.py", receipt)]], receipt=receipt)
    assert v.refused is not None and "src/evil.py" in v.refused
    assert v.oversized_mini == ["src/evil.py"]


def test_rename_inherits_from_an_old_path_declared_in_files():
    rec = _record(files=["src/old.py"], design_paths=["src/x.py"])
    v = _close(rec, [[("R100", "src/new.py", "src/old.py")]])
    assert v.oversized_mini == ["src/old.py"]


def test_scored_status_letters_are_read_by_their_first_letter():
    tl = _module()
    assert tl.is_new_source("C075", "src/c.py") is True
    rows = [("A", "src/a.py", None), ("A", "src/b.py", None), ("C100", "src/c.py", "src/a.py")]
    rec = _record(design_paths=["src/a.py", "src/b.py", "src/c.py"])
    v = _close(rec, [rows])
    assert "new-source" in v.upgrade
    assert tl.classify_commit(rows, repo_kind="project", sync_regex="") == "chain: new-source"
    carry = [[("R100", "src/core.py", "src/app.py")], [("M", "src/core.py", None)]]
    assert _close(_record(), carry).refused is None


def test_sync_path_run_in_a_worktree_may_commit_several_times():
    rec = _record(sync_hits={"scripts/enforcement/x.py"}, in_worktree=True)
    commits = [[("M", "src/app.py", None)], [("M", "src/app.py", None)]]
    v = _close(rec, commits, verb="done")
    assert v.refused is None
    assert not any(f.startswith("sync:") for f in v.findings)


def test_sync_multi_commit_is_a_finding_on_blocked_and_handoff():
    rec = _record(sync_hits={"scripts/enforcement/x.py"})
    commits = [[("M", "src/app.py", None)], [("M", "src/app.py", None)]]
    for verb in ("blocked", "handoff"):
        v = _close(rec, commits, verb=verb)
        assert v.refused is None, verb
        assert any(f.startswith("sync:") and "once" in f for f in v.findings), verb


def test_started_at_is_required():
    tl = _module()
    try:
        tl.LaneRecord(stamped=True, design_paths=["src/app.py"])
    except TypeError:
        return
    raise AssertionError("LaneRecord built without started_at")


def test_new_source_added_then_deleted_does_not_count():
    rec = _record(design_paths=["src/app.py", "src/a.py", "src/b.py", "src/c.py"])
    commits = [
        [("A", "src/a.py", None), ("A", "src/b.py", None), ("A", "src/c.py", None)],
        [("D", "src/a.py", None)],
    ]
    v = _close(rec, commits)
    assert "new-source" not in v.upgrade
    assert v.needs_full_review is False


def test_new_source_renamed_moves_the_counted_path():
    rec = _record(design_paths=["src/a.py", "src/b.py", "src/c.py", "src/d.py"])
    commits = [
        [("A", "src/a.py", None), ("A", "src/b.py", None)],
        [("R100", "src/d.py", "src/b.py")],
    ]
    v = _close(rec, commits)
    assert "new-source" not in v.upgrade
    commits.append([("A", "src/c.py", None)])
    assert "new-source" in _close(rec, commits).upgrade


def test_new_source_same_path_added_twice_counts_once():
    rec = _record(design_paths=["src/a.py", "src/b.py"])
    commits = [[("A", "src/a.py", None)], [("A", "src/a.py", None), ("A", "src/b.py", None)]]
    assert "new-source" not in _close(rec, commits).upgrade


def test_all_four_upgrade_tokens_in_order():
    rows = [
        ("M", "specs/services/x.yaml", None),
        ("A", "src/a.py", None),
        ("A", "src/b.py", None),
        ("A", "src/c.py", None),
    ]
    rec = _record(
        appetite=10,
        behaviours=8,
        design_paths=["specs/services/x.yaml", "src/a.py", "src/b.py", "src/c.py"],
    )
    v = _close(rec, [rows], minutes=21)
    assert v.upgrade == ["contract", "new-source", "behaviours", "appetite"]


def test_new_source_upgrade_line_names_the_review_receipt():
    rec = _record(design_paths=["src/a.py", "src/b.py", "src/c.py"])
    rows = [("A", "src/a.py", None), ("A", "src/b.py", None), ("A", "src/c.py", None)]
    line = [f for f in _close(rec, [rows]).findings if f.startswith("UPGRADE: new-source")]
    assert line and "--review" in line[0]


def test_design_paths_and_amendments_are_normalised():
    rec = _record(design_paths=["./src/app.py"], amendments=[" src/x//y.py "])
    v = _close(rec, [[("M", "src/app.py", None), ("M", "src/x/y.py", None)]])
    assert v.refused is None
    assert v.amended_paths == ["src/x/y.py"]


def test_unstamped_receipt_is_exempt():
    receipt = "docs/development/reviews/2026-10-02-x-review.md"
    rec = _record(stamped=False, files=["src/app.py"])
    v = _close(rec, [[("M", "src/app.py", None), ("A", receipt, None)]], receipt=receipt)
    assert v.oversized_mini == []


# ── round-2 fix ──────────────────────────────────────────────────────────────────────────


def test_receipt_path_is_normalised_on_both_closes():
    committed = "docs/development/reviews/r.md"
    rows = [("M", "src/app.py", None), ("A", committed, None)]
    for spelled in ("./" + committed, " " + committed + " "):
        stamped = _close(_record(), [rows], receipt=spelled)
        assert stamped.refused is None, spelled
        assert stamped.oversized_mini == [], spelled
        unstamped = _close(_record(stamped=False), [rows], receipt=spelled)
        assert unstamped.oversized_mini == [], spelled


# ── T08-D7 ───────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("bad", [None, "1000", True, float("nan"), float("inf"), -float("inf")])
def test_d_h1_a_record_without_a_finite_numeric_start_cannot_be_built(bad):
    with pytest.raises(TypeError):
        _record(started_at=bad)


@pytest.mark.parametrize("good", [0, 1_000_000, 1_000_000.5])
def test_d_h1_an_int_or_float_start_is_accepted(good):
    assert _record(started_at=good).started_at == good


def test_d_o8_the_docstring_puts_only_the_count_on_the_feedback_row():
    doc = " ".join(_module().measure_close.__doc__.split())
    assert "``design_amends`` and ``amended_paths`` go on the feedback row" not in doc
    assert "the feedback row carries ``design_amends``" in doc
    assert "``amended_paths`` is the ``CloseVerdict``'s own detail" in doc
