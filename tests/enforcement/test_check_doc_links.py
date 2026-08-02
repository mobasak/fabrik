# AFTER-EDIT: scripts/enforcement/check_doc_links.py
"""Behavior contract for the link-integrity gate (docs-truth plan Phase F)."""

import subprocess
import sys
from pathlib import Path

REPO = Path("/opt/fabrik")
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))

import check_doc_links as cdl  # noqa: E402


def test_live_tree_is_clean():
    """The converged tree has zero broken references (the gate's green baseline)."""
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts/enforcement/check_doc_links.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_missing_target_is_broken():
    src = REPO / "docs" / "QUICKSTART.md"
    assert cdl._resolves("docs/this-file-does-not-exist-xyz.md", src) is False


def test_existing_target_resolves_root_and_relative():
    src = REPO / "docs" / "operations" / "deployment.md"
    assert cdl._resolves("docs/QUICKSTART.md", src) is True  # repo-root form
    assert cdl._resolves("../QUICKSTART.md", src) is True  # file-relative form


def test_placeholder_and_external_are_exempt():
    src = REPO / "docs" / "QUICKSTART.md"
    assert cdl._resolves("docs/development/plans/YYYY-MM-DD-plan-x.md", src) is True
    assert cdl._resolves("https://example.org/x.md", src) is True
    assert cdl._resolves("specs/services/my-api.yaml", src) is True


def test_project_context_allowlist_is_exempt():
    src = REPO / "CLAUDE.md"
    assert cdl._resolves("docs/DEPLOYMENT.md", src) is True  # project-side doc name


def test_fenced_and_stale_marked_lines_are_skipped():
    text = "para docs/nope-a.md\n```\ndocs/nope-b.md\n```\n⚠ docs/nope-c.md absent\n"
    bare = [t for t, k in cdl._iter_refs(text) if k == "bare"]
    assert "docs/nope-a.md" in bare
    assert "docs/nope-b.md" not in bare  # fenced
    assert "docs/nope-c.md" not in bare  # documented-stale marker


def test_archive_sources_are_excluded():
    srcs = {str(p.relative_to(REPO)) for p in cdl._tracked_md_sources()}
    assert not any(s.startswith("docs/archive/") for s in srcs)
    assert not any(s.startswith("docs/infrastructure/archive/") for s in srcs)
    assert "docs/LESSONS_LEARNT.md" not in srcs  # dated ledger exempt


def test_scaffold_templates_are_excluded_as_sources():
    # Templates carry intentional placeholder refs (a project's own future files).
    # They must never be link-checked — in a project they land under docs/ and would
    # false-flag every scaffolded copy (the /opt/seo AI's 21-of-28 template artifacts).
    assert cdl._is_template_source("docs/reference/scaffold-templates/FEATURES_TEMPLATE.md")
    assert cdl._is_template_source("docs/QUICKSTART_TEMPLATE.md")
    assert cdl._is_template_source("docs/reference/scaffold-templates/whatever.md")
    assert not cdl._is_template_source("docs/QUICKSTART.md")
    assert not cdl._is_template_source("docs/reference/a-real-doc.md")
    # and none survive into the real source list
    srcs = {str(p.relative_to(REPO)) for p in cdl._tracked_md_sources()}
    assert not any(s.endswith("_TEMPLATE.md") or "scaffold-templates/" in s for s in srcs)
