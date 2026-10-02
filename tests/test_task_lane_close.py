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

ROOT = Path(__file__).resolve().parents[1]
SYNC_REGEX = r"^(scripts/enforcement/|\.windsurf/rules/)"


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
    assert _module().classify_commit(rows, repo_kind="project", sync_regex="") == "chain: new-source"


def test_new_source_counted_across_commits():
    rec = _record(design_paths=["src/one.py", "src/two.py", "src/three.py"])
    commits = [[("A", "src/one.py", None), ("A", "src/two.py", None)], [("A", "src/three.py", None)]]
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
    v = _close(_record(amendments=["src/other.py"]), [UNDECLARED], verb="done")
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
    rec = _record(stamped=False, files=["src/app.py"], design_paths=[], behaviours=9, appetite=1)
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
