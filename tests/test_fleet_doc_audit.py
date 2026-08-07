# AFTER-EDIT: scripts/fleet_doc_audit.py | none
"""Behavior contract for the fleet doc-freshness audit's pure probes."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fleet_doc_audit as fda  # noqa: E402


def test_lag_days_code_leads_docs():
    assert fda.lag_days(100 * 86400, 79 * 86400) == 21


def test_lag_days_docs_current_or_newer_is_zero():
    assert fda.lag_days(100 * 86400, 100 * 86400) == 0
    assert fda.lag_days(100 * 86400, 200 * 86400) == 0


def test_lag_days_no_code_commits_is_zero():
    assert fda.lag_days(None, 50 * 86400) == 0


def test_stub_hits_counts_template_sentinels():
    text = "# [Project Name]\n\n**Last Updated:** YYYY-MM-DD\n\n- goal: [TBD — fill]\n- ok line\n"
    assert fda.stub_hits(text) == 3


def test_stub_hits_filled_doc_is_clean():
    text = "# seo\n\n**Last Updated:** 2026-08-07\n\n- goal: rank tracking\n"
    assert fda.stub_hits(text) == 0


def test_required_docs_compares_basenames_against_registry(tmp_path):
    # Day-review regression: the allowlist carries BARE basenames while KEY_DOCS
    # are docs/-prefixed — the naive membership test made the MISSING probe dead
    # code fleet-wide on first ship.
    (tmp_path / "project.yaml").write_text("type: python-api\n", encoding="utf-8")
    req = fda._required_docs(tmp_path)
    assert "docs/SERVICES.md" in req and "docs/RESILIENCE.md" in req


def test_audit_project_docs_never_committed_is_labeled_not_epoch(tmp_path):
    # Day-review regression: docs/ with zero git history must read as its own
    # failure mode, never an epoch-sized (~20,000d) lag that tops the report.
    import subprocess as sp

    sp.run(["git", "init", "-q"], cwd=tmp_path, check=True, timeout=15)
    sp.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True, timeout=15)
    sp.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True, timeout=15)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "m.py").write_text("x=1\n", encoding="utf-8")
    sp.run(["git", "-C", str(tmp_path), "add", "src/m.py"], check=True, timeout=15)
    sp.run(["git", "-C", str(tmp_path), "commit", "-qm", "code"], check=True, timeout=15)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "notes.md").write_text("n\n", encoding="utf-8")  # untracked
    row = fda.audit_project(tmp_path)
    assert row is not None
    assert row.lag < 3650, f"epoch inflation: {row.lag}"
    assert any("never committed" in s for s in row.stale)
