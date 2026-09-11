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


def test_every_per_run_artifact_class_is_excluded_including_certifications():
    """All FOUR dated, machine-generated, per-run classes — asserted LITERALLY and together,
    because certifications arrived (2026-08-27) without this exclusion and nothing noticed: one
    synced command MANDATED `docs/development/certifications/` while this synced check penalised
    it, so every project reddened its gate on its first certification (job-agent: 16 ERRORs, then
    16 rows of per-run noise injected into a curated index as the workaround).

    INDEX.md maps DURABLE docs. Board shape, ticket naming, dispositions and evidence paths are
    already graded by check_certification_coverage.py — that is the check that owns them."""
    for prefix in (
        "docs/development/plans/",
        "docs/development/epics/",
        "docs/development/reviews/",
        "docs/development/certifications/",
    ):
        assert prefix in cdi.EXCLUDE_PREFIXES, f"{prefix} must be exempt from the INDEX map"


def test_a_certification_board_file_is_not_reported_as_unindexed():
    """The behaviour, not the constant: the path shape /fabrik-user-test actually emits."""
    board = "docs/development/certifications/2026-08-28-cert-linkedin/TC01-profiles.md"
    assert any(board.startswith(p) for p in cdi.EXCLUDE_PREFIXES), board


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


def test_untracked_doc_fires_on_the_authoring_run(monkeypatch):
    """transdoc 01M17VA9: tracked-only scoping gave the run that CREATES a doc a false
    green — it committed on it, and the missing INDEX row surfaced as the next agent's
    red. An untracked doc under the INDEX-governed tree is live and must be reported
    to its author, on the run that wrote it."""
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        if "ls-files" in cmd:

            class R:
                stdout = "docs/reference/brand-new-proposal.md\n" if "--others" in cmd else ""

            return R()
        return real_run(cmd, **kw)

    monkeypatch.setattr(cdi.subprocess, "run", fake_run)
    rc = cdi.main()
    assert rc == 1


def _fake_ls(monkeypatch, *, tracked="", untracked=""):
    """Stand in for both `git ls-files` calls — the second is the one carrying --others."""
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        if "ls-files" in cmd:

            class R:
                stdout = untracked if "--others" in cmd else tracked

            return R()
        return real_run(cmd, **kw)

    monkeypatch.setattr(cdi.subprocess, "run", fake_run)


def _isolated_index(monkeypatch, tmp_path, body="# INDEX\n\n- [README](README.md)\n"):
    """Point the check at a throwaway root whose INDEX.md names nothing under docs/.

    Without this the check reads the HUB's own INDEX.md, which DOES carry a DECISIONS.md
    row — so an exemption test run against the live tree passes identically whether or not
    the exemption exists. That vacuous shape is exactly what these three tests must avoid.
    """
    (tmp_path / "INDEX.md").write_text(body, encoding="utf-8")
    monkeypatch.setattr(cdi, "REPO", tmp_path)


def test_seeded_ledger_is_exempt_while_it_is_still_untracked(monkeypatch, tmp_path):
    """20 of the 45 git repos under /opt sit in exactly this state (measured 2026-09-11):
    the hub's governance sync wrote docs/DECISIONS.md, no session in that repo authored it,
    nobody ever committed it — and this gate then billed the INDEX row to whoever happened
    to run next. The untracked-counts-as-live rule assumes an author; a seeded file has none."""
    _isolated_index(monkeypatch, tmp_path)
    _fake_ls(monkeypatch, tracked="", untracked="docs/DECISIONS.md\n")
    assert cdi.main() == 0


def test_an_adopted_ledger_still_owes_its_index_row(monkeypatch, tmp_path):
    """The exemption is keyed on TRACKED-NESS, not on the path — which is the whole reason
    docs/DECISIONS.md is not simply an EXCLUDE_EXACT entry. The moment a repo commits its
    ledger it is that project's own durable doc and owes its row like any other; 9 of the 45
    are already in that state, and a blanket path exemption would have silenced all nine."""
    _isolated_index(monkeypatch, tmp_path)
    _fake_ls(monkeypatch, tracked="docs/DECISIONS.md\n", untracked="")
    assert cdi.main() == 1


def test_missing_index_is_a_finding_not_a_traceback(monkeypatch, tmp_path, capsys):
    """5 of the 45 repos carry this synced check and have no INDEX.md at all; the unguarded
    read raised FileNotFoundError, so the gate reported a stack trace — which names no file
    to fix and reads as a broken check rather than a finding."""
    monkeypatch.setattr(cdi, "REPO", tmp_path)  # deliberately no INDEX.md
    assert cdi.main() == 1
    assert "INDEX.md is missing" in capsys.readouterr().out
