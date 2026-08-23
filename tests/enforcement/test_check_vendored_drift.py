# AFTER-EDIT: scripts/enforcement/check_vendored_drift.py
"""Vendored-drift report — the sync-exclusion blind spot gets a measuring instrument."""

import subprocess
import sys
from pathlib import Path

CHECK = Path("/opt/fabrik/scripts/enforcement/check_vendored_drift.py")

sys.path.insert(0, str(CHECK.parent))
import check_vendored_drift as cvd  # noqa: E402


def _tree(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)


def test_self_skips_outside_the_hub(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert cvd.main() == 0
    assert capsys.readouterr().out == "", "outside the hub the check must be silent"


def test_classification_and_allowlist(tmp_path, capsys, monkeypatch):
    """identical / declared-design / UNREVIEWED / local-only, with the repo-owned allowlist
    splitting design from debt; sync-managed repos (synced.lock) and the hub are skipped."""
    hub = tmp_path / "fabrik"
    _tree(hub, {
        "scripts/enforcement/check_a.py": "A\n",
        "scripts/enforcement/check_b.py": "B\n",
        "scripts/final_gate.py": "G\n",
        "scripts/select_rules.py": "S\n",
        "scripts/review_rubric.py": "R\n",
    })
    vendor = tmp_path / "vendorer"
    _tree(vendor, {
        "scripts/enforcement/check_a.py": "A\n",            # identical
        "scripts/enforcement/check_b.py": "B-local\n",       # differs → allowlisted = design
        "scripts/final_gate.py": "G-old\n",                  # differs → UNREVIEWED
        "scripts/enforcement/check_mine.py": "M\n",          # local-only
        ".fabrik/vendored-divergence-allowlist":
            "# deliberate strip\nscripts/enforcement/check_b.py\n",
    })
    managed = tmp_path / "managed"
    _tree(managed, {
        "scripts/enforcement/check_a.py": "STALE\n",
        ".fabrik/synced.lock": "{}",
    })
    monkeypatch.setattr(cvd, "HUB", hub)
    monkeypatch.setattr(cvd, "OPT", tmp_path)
    monkeypatch.chdir(hub)
    assert cvd.main() == 0
    out = capsys.readouterr().out
    assert "vendorer: 1 identical · 1 declared-design · 1 UNREVIEWED diff · 1 local-only" in out
    assert "vendorer/scripts/final_gate.py: differs from hub with no declaration" in out
    assert "check_b.py: differs" not in out, "an allowlisted divergence must not be flagged"
    assert "managed" not in out, "a sync-managed repo is the governance-sync's business"
    assert out.startswith("⚠"), "unreviewed divergence must use the emitter's ⚠-first opt-in"


def test_quiet_when_everything_is_declared(tmp_path, capsys, monkeypatch):
    hub = tmp_path / "fabrik"
    _tree(hub, {"scripts/enforcement/check_a.py": "A\n", "scripts/final_gate.py": "G\n",
                "scripts/select_rules.py": "S\n", "scripts/review_rubric.py": "R\n"})
    vendor = tmp_path / "v2"
    _tree(vendor, {
        "scripts/enforcement/check_a.py": "A-strip\n",
        ".fabrik/vendored-divergence-allowlist": "scripts/enforcement/check_a.py\n",
    })
    monkeypatch.setattr(cvd, "HUB", hub)
    monkeypatch.setattr(cvd, "OPT", tmp_path)
    monkeypatch.chdir(hub)
    assert cvd.main() == 0
    out = capsys.readouterr().out
    assert out.startswith("check_vendored_drift: OK"), out


def test_real_script_runs_clean_at_repo_root():
    r = subprocess.run([sys.executable, str(CHECK)], capture_output=True, text=True,
                       timeout=30, cwd="/opt/fabrik")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip(), "at the hub the report always says something"
