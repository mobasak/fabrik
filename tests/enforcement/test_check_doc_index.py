# AFTER-EDIT: scripts/enforcement/check_doc_index.py
"""Behavior contract for the INDEX↔tree drift gate (docs-truth plan Phase F)."""

import subprocess
import sys
from pathlib import Path

REPO = Path("/opt/fabrik")
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))

import check_doc_index as cdi  # noqa: E402


def test_live_tree_is_clean():
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts/enforcement/check_doc_index.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_selection_docs_are_excluded():
    assert cdi._SELECTION_RE.match("docs/reference/kilo/TASK_SUBAGENT_SELECTION.md")
    assert cdi._SELECTION_RE.match("docs/reference/kilo/TTS_SELECTION.md")
    assert not cdi._SELECTION_RE.match("docs/reference/kilo/AI_VENDOR_ACCESS.md")


def test_pipeline_artifacts_are_excluded():
    assert any(p.startswith("docs/development/plans/") for p in cdi.EXCLUDE_PREFIXES)
    assert any(p.startswith("docs/superpowers/") for p in cdi.EXCLUDE_PREFIXES)


def test_would_fail_on_unindexed_doc(monkeypatch):
    """(b)-direction detection: a live doc absent from INDEX is reported."""
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        if "ls-files" in cmd:

            class R:  # minimal stand-in
                stdout = "docs/operations/definitely-not-indexed-xyz.md\n"

            return R()
        return real_run(cmd, **kw)

    monkeypatch.setattr(cdi.subprocess, "run", fake_run)
    rc = cdi.main()
    assert rc == 1


def test_ls_files_disables_quotepath(monkeypatch):
    """quotePath regression (trade-intelligence upstream 2026-08-05): the ls-files
    call must pass -c core.quotePath=false or non-ASCII doc names come back
    escaped and false-flag as missing from INDEX.md."""
    captured = {}
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        if "ls-files" in cmd:
            captured["cmd"] = cmd

            class R:
                stdout = ""

            return R()
        return real_run(cmd, **kw)

    monkeypatch.setattr(cdi.subprocess, "run", fake_run)
    cdi.main()
    assert "core.quotePath=false" in captured["cmd"], captured
