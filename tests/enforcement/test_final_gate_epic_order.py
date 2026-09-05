"""`epic_order --check` as an optional Tier-2 gate row (plan 2026-09-03-plan-1-multi-agent-per-repo,
T05b; audit R7 — the integrity proof existed but no gate ever ran it).

Two guards, both graded here by EXECUTION against a scratch project (never the hub's own epics
dir for the failing case): the row exists only where `scripts/epic_order.py` exists (the script
is in no synced manifest — a project without it must see NO row, never a failure pointing at a
missing file), and an absent `docs/development/epics/` is a LABELLED skip that `skipped_checks`
lists — the shipped `bandit (NOT INSTALLED — skipped)` convention: a True row whose NAME says it
did not run. One integrity finding must red the check and reach the JSON verbatim.

Fixture epics are shaped so their verdict cannot depend on a finding class a sibling ticket may
add to `check_integrity`: the red fixture is a file with no frontmatter (the parser-level class),
the green fixture is two epics in DIFFERENT phases with disjoint `owned_paths`.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parents[2]
GATE = HUB / "scripts" / "final_gate.py"
EPIC_ORDER = HUB / "scripts" / "epic_order.py"

CHECK = "epic_order --check"
NA_LABEL = "epic_order --check (N/A — no docs/development/epics/)"

_EPIC = """---
kind: story
title: "Epic {n} — {name}"
status: 0
epic_n: {n}
slug: {slug}
depends_on: {deps}
parallel_with: []
owned_paths: ["{path}"]
owner: ""
scaffold: none
port: 0
target_vps: vps1
---
## Epic {n} — {name}
"""


def _load_gate_at(root: Path, monkeypatch):
    """`PROJECT_ROOT = Path.cwd()` is read at import — chdir first, then load a fresh module."""
    monkeypatch.chdir(root)
    spec = importlib.util.spec_from_file_location("final_gate_epic_order_under_test", GATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _project(tmp_path: Path, *, with_script: bool = True) -> Path:
    if with_script:
        (tmp_path / "scripts").mkdir()
        shutil.copy(EPIC_ORDER, tmp_path / "scripts" / "epic_order.py")
    return tmp_path


def _clean_epics(root: Path) -> Path:
    d = root / "docs" / "development" / "epics"
    d.mkdir(parents=True)
    (d / "2026-01-01-epic-1-alpha.md").write_text(
        _EPIC.format(n=1, name="Alpha", slug="alpha", deps="[]", path="src/alpha/**")
    )
    (d / "2026-01-01-epic-2-beta.md").write_text(
        _EPIC.format(n=2, name="Beta", slug="beta", deps="[1]", path="src/beta/**")
    )
    return d


def _row(results, name):
    hits = [r for r in results if r[0] == name]
    assert len(hits) == 1, f"expected exactly one {name!r} row, got {hits!r}"
    return hits[0]


# (a) script present, no epics dir → the LABELLED skip, listed under skipped_checks
def test_no_epics_dir_is_a_labelled_skip_that_skipped_checks_lists(tmp_path, monkeypatch):
    fg = _load_gate_at(_project(tmp_path), monkeypatch)
    row = _row(fg.run_consistency_checks(tier=2, check_only=True), NA_LABEL)
    assert row[1] is True  # green by contract — a skip never traps an agent …
    assert row[2].lstrip().startswith("⚠")  # … but it says so where --json `warnings` reads
    # … and the JSON's `skipped_checks` (the field CLAUDE.md tells the reader to pair with
    # `status`) names it — the consumer's real field, not the label alone.
    assert fg._summarize_skipped([row]) == {"skipped": 1, "skipped_checks": [CHECK]}


# (b) a FIXTURE dir with one integrity finding → the check fails, the finding reaches the JSON
def test_one_integrity_finding_fails_the_check_and_reaches_the_json(tmp_path, monkeypatch):
    root = _project(tmp_path)
    d = root / "docs" / "development" / "epics"
    d.mkdir(parents=True)
    (d / "2026-01-01-epic-1-legacy.md").write_text("# Epic — legacy, no frontmatter\n")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    proc = subprocess.run(
        [sys.executable, str(GATE), "--check", "--json"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=600,
    )
    payload = json.loads(proc.stdout)
    assert payload["status"] == "failure"
    failed = {f["check"]: f["output"] for f in payload["failures"]}
    assert CHECK in failed, sorted(failed)
    assert "no frontmatter" in failed[CHECK]
    assert "2026-01-01-epic-1-legacy.md" in failed[CHECK]
    assert CHECK not in payload["skipped_checks"]


# (c) the hub's own epics dir, as it stands after the legacy epic got its frontmatter → green
def test_hub_epics_dir_passes(monkeypatch):
    fg = _load_gate_at(HUB, monkeypatch)
    assert fg._epic_order_row() == (CHECK, True, "")


# (d) a project without scripts/epic_order.py → no row at all
def test_no_script_means_no_row(tmp_path, monkeypatch):
    fg = _load_gate_at(_project(tmp_path, with_script=False), monkeypatch)
    assert fg._epic_order_row() is None
    names = [r[0] for r in fg.run_consistency_checks(tier=2, check_only=True)]
    assert not [n for n in names if "epic_order" in n], names


# (e) dir present, integrity clean → passes, and the run's failing set is unchanged
def test_clean_dir_passes_and_leaves_the_overall_status_unchanged(tmp_path, monkeypatch):
    root = _project(tmp_path)
    fg = _load_gate_at(root, monkeypatch)
    before = {r[0] for r in fg.run_consistency_checks(tier=2, check_only=True) if not r[1]}
    _clean_epics(root)
    results = fg.run_consistency_checks(tier=2, check_only=True)
    assert _row(results, CHECK) == (CHECK, True, "")
    assert {r[0] for r in results if not r[1]} == before


# Tier membership by execution: --lean's count must not move (the Phase Tests regression class).
def test_lean_tier_never_runs_it(tmp_path, monkeypatch):
    root = _project(tmp_path)
    _clean_epics(root)
    fg = _load_gate_at(root, monkeypatch)
    names = [r[0] for r in fg.run_consistency_checks(tier=1, check_only=True)]
    assert not [n for n in names if "epic_order" in n], names
    assert CHECK in [r[0] for r in fg.run_consistency_checks(tier=2, check_only=True)]
