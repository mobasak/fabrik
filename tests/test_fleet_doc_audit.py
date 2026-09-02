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


# ── INDEX self-indexing (added 2026-09-02) ───────────────────────────────────────────────
# THE DEFECT: the weekly cron wrote a new dated report every Monday and never touched
# INDEX.md, so check_doc_index went red for whoever ran the next unrelated gate — three
# earlier reports had been indexed BY HAND after the fact. Fixed at the generator; these
# tests are the guard, seen red before the helper existed.

_ANCHOR = "| [fleet-doc-audit-latest.md](docs/infrastructure/probe-reports/fleet-doc-audit-latest.md) | Newest fleet doc-freshness report |\n"


def _index(tmp_path, body: str):
    p = tmp_path / "INDEX.md"
    p.write_text(body, encoding="utf-8")
    return p


def test_ensure_index_row_inserts_exactly_one_row_before_the_latest_anchor(tmp_path):
    p = _index(tmp_path, "| a | b |\n" + _ANCHOR + "| z | z |\n")
    assert fda.ensure_index_row(p, "fleet-doc-audit-2026-09-02.md", "2026-09-02") is True
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines[1].startswith(
        "| [fleet-doc-audit-2026-09-02.md](docs/infrastructure/probe-reports/fleet-doc-audit-2026-09-02.md) |"
    )
    assert "2026-09-02" in lines[1]
    assert lines[2] == _ANCHOR.rstrip("\n"), (
        "the row must sit immediately BEFORE the -latest anchor"
    )
    assert sum("fleet-doc-audit-2026-09-02.md" in ln for ln in lines) == 1


def test_ensure_index_row_is_idempotent(tmp_path):
    p = _index(tmp_path, _ANCHOR)
    assert fda.ensure_index_row(p, "fleet-doc-audit-2026-09-02.md", "2026-09-02") is True
    before = p.read_text(encoding="utf-8")
    assert fda.ensure_index_row(p, "fleet-doc-audit-2026-09-02.md", "2026-09-02") is False
    assert p.read_text(encoding="utf-8") == before


def test_ensure_index_row_without_anchor_changes_nothing_and_says_so(tmp_path):
    p = _index(tmp_path, "| a | b |\n")
    assert fda.ensure_index_row(p, "fleet-doc-audit-2026-09-02.md", "2026-09-02") is False
    assert p.read_text(encoding="utf-8") == "| a | b |\n"


def test_ensure_index_row_finds_the_anchor_by_link_target_not_link_text(tmp_path):
    # F2 (scoped review 2026-09-02): a full-prefix match broke on any edit to the anchor row's
    # link text/description and failed only into a cron log nobody reads. Match the TARGET.
    p = _index(
        tmp_path,
        "| [latest audit](docs/infrastructure/probe-reports/fleet-doc-audit-latest.md) | some other wording |\n",
    )
    assert fda.ensure_index_row(p, "fleet-doc-audit-2026-09-02.md", "2026-09-02") is True
    assert "[fleet-doc-audit-2026-09-02.md](" in p.read_text(encoding="utf-8").splitlines()[0]


def test_index_is_clean_treats_a_staged_sibling_edit_as_dirty(tmp_path):
    # F1 (scoped review 2026-09-02, reproduced live): `git diff --quiet -- INDEX.md` compares the
    # worktree to the INDEX, so a sibling's staged-but-uncommitted edit read as clean and would be
    # swept into the cron's commit. The fail-safe must compare against HEAD.
    import subprocess

    def git(*a):
        return subprocess.run(
            ["git", "-C", str(tmp_path), *a], check=True, capture_output=True, text=True
        )

    git("init", "-q", ".")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (tmp_path / "INDEX.md").write_text("base\n", encoding="utf-8")
    git("add", "INDEX.md")
    git("commit", "-qm", "base")
    assert fda.index_is_clean(tmp_path) is True
    (tmp_path / "INDEX.md").write_text("base\nSIBLING STAGED EDIT\n", encoding="utf-8")
    git("add", "INDEX.md")  # staged, not committed — the trap
    assert fda.index_is_clean(tmp_path) is False
