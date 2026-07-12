"""Behavior-Contract tests for the capability doc-audit (plan-2 Phase B).

Risk-ordered: the DESTRUCTIVE path first (dry-run-by-default; --apply deletes a dead doc; a tool file is
NEVER touched), then undocumented-stub / doc_drift routing, then idempotence.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "audit_capability_docs",
    Path(__file__).resolve().parent.parent / "scripts" / "audit_capability_docs.py",
)
aud = importlib.util.module_from_spec(_SPEC)
sys.modules["audit_capability_docs"] = aud
_SPEC.loader.exec_module(aud)  # type: ignore


def _write_catalog(tmp_path: Path, caps: list[dict]) -> Path:
    cj = tmp_path / "capabilities.json"
    cj.write_text(json.dumps({"generated_at": "2026-07-12T00:00:00+00:00", "capabilities": caps}))
    return cj


# --- Behavior 1 [RISK, TDD]: dry-run default; --apply deletes dead doc; a tool file is never touched ---

def test_dead_doc_deleted_and_tool_never_removed(tmp_path) -> None:
    orphan = tmp_path / "docs" / "orphan.md"
    orphan.parent.mkdir(parents=True)
    orphan.write_text("dead doc\n")
    tool = tmp_path / "scripts" / "retired_tool.py"
    tool.parent.mkdir(parents=True)
    tool.write_text("# code\n")
    cj = _write_catalog(tmp_path, [
        {"name": "orphan", "kind": "script", "summary": "", "invoke": "", "status": "ok",
         "defects": ["dead_doc"], "doc_link": "docs/orphan.md", "verified_at": "x"},
        {"name": "scripts/retired_tool.py", "kind": "script", "summary": "", "invoke": "python x",
         "status": "retired", "defects": ["retired"], "doc_link": "INDEX.md", "verified_at": "x"},
    ])
    # (a) default = dry-run → lists the dead doc but does NOT delete
    rep = aud.run(cj, apply=False, root=tmp_path)
    assert orphan.exists(), "dry-run must not delete"
    assert any("orphan.md" in f for f in rep["fixed"]), rep["fixed"]
    # (b) --apply → the dead doc is unlinked
    rep2 = aud.run(cj, apply=True, root=tmp_path)
    assert not orphan.exists(), "apply must delete the dead doc"
    # (c) the retired tool is surfaced for the operator and its own file is untouched in BOTH modes
    assert tool.exists(), "a tool file must NEVER be unlinked"
    assert any(o["defect"] == "retired" and "retired_tool" in o["name"] for o in rep2["operator_action"])


def test_apply_never_unlinks_a_non_markdown_path(tmp_path) -> None:
    """Even if a dead_doc's doc_link points at a .py/.sh (a tool), --apply must refuse to unlink it."""
    tool = tmp_path / "scripts" / "tool.py"
    tool.parent.mkdir(parents=True)
    tool.write_text("# code\n")
    cj = _write_catalog(tmp_path, [
        {"name": "x", "kind": "script", "summary": "", "invoke": "python x", "status": "ok",
         "defects": ["dead_doc"], "doc_link": "scripts/tool.py", "verified_at": "x"},
    ])
    aud.run(cj, apply=True, root=tmp_path)
    assert tool.exists(), "a non-.md doc_link (a tool) must never be unlinked"


def test_apply_never_deletes_outside_repo_root(tmp_path) -> None:
    """CRITICAL: --apply must NEVER unlink a .md that escapes `root` via an absolute path, `../`
    traversal, or a symlinked intermediate dir — even from an untrusted catalog (destroying another
    project's / another AI's files is a critical failure). Each escape is SKIPPED + surfaced, not deleted."""
    outside = tmp_path.parent / f"pwn-trav-{tmp_path.name}.md"
    outside.write_text("victim\n")
    abs_target = tmp_path.parent / f"pwn-abs-{tmp_path.name}.md"
    abs_target.write_text("victim2\n")
    outside_dir = tmp_path.parent / f"pwn-dir-{tmp_path.name}"
    outside_dir.mkdir()
    (outside_dir / "x.md").write_text("victim3\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "link").symlink_to(outside_dir, target_is_directory=True)
    try:
        cj = _write_catalog(tmp_path, [
            {"name": "trav", "kind": "script", "summary": "", "invoke": "", "status": "ok",
             "defects": ["dead_doc"], "doc_link": "../" + outside.name, "verified_at": "x"},
            {"name": "abs", "kind": "script", "summary": "", "invoke": "", "status": "ok",
             "defects": ["dead_doc"], "doc_link": str(abs_target), "verified_at": "x"},
            {"name": "symlink", "kind": "script", "summary": "", "invoke": "", "status": "ok",
             "defects": ["dead_doc"], "doc_link": "docs/link/x.md", "verified_at": "x"},
        ])
        rep = aud.run(cj, apply=True, root=tmp_path)
        assert outside.exists(), "`../` traversal escaped root and deleted a file"
        assert abs_target.exists(), "absolute path escaped root and deleted a file"
        assert (outside_dir / "x.md").exists(), "symlinked intermediate dir escaped root"
        skipped = [o for o in rep["operator_action"] if o["defect"] == "dead_doc"]
        assert len(skipped) == 3, f"all 3 escapes must be surfaced as SKIPPED, got {skipped}"
    finally:
        outside.unlink(missing_ok=True)
        abs_target.unlink(missing_ok=True)
        (outside_dir / "x.md").unlink(missing_ok=True)
        outside_dir.rmdir()


def test_malformed_or_keyless_catalog_still_writes_report(tmp_path) -> None:
    """A malformed / `capabilities`-less catalog → empty audit but the report is STILL written (never a
    crash mid-run that leaves partial changes)."""
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    rep = aud.run(bad, apply=False, root=tmp_path)
    assert rep == {"fixed": [], "operator_action": []}
    assert (tmp_path / "docs" / "development" / "capability-defects.md").exists()
    nokey = tmp_path / "nokey.json"
    nokey.write_text('{"generated_at": "x"}')
    assert aud.run(nokey, apply=False, root=tmp_path) == {"fixed": [], "operator_action": []}


def test_record_missing_or_nonstring_name_does_not_crash(tmp_path) -> None:
    """A record with a missing OR non-string `name` must not crash mid-loop (which could abort after a
    partial --apply and skip the report). Covers both `.get` default and a `str()` coercion of e.g. an int."""
    cj = _write_catalog(tmp_path, [{"kind": "script", "defects": ["undocumented"], "doc_link": None}])
    rep = aud.run(cj, apply=True, root=tmp_path)
    assert any("unnamed" in f for f in rep["fixed"]), rep["fixed"]
    # a legit in-root dead_doc FIRST, then a non-string-name record — the run must complete + write the report
    dead = tmp_path / "docs" / "dead.md"
    dead.parent.mkdir(parents=True, exist_ok=True)
    dead.write_text("x\n")
    cj2 = _write_catalog(tmp_path, [
        {"name": "d", "kind": "script", "summary": "", "invoke": "", "status": "ok",
         "defects": ["dead_doc"], "doc_link": "docs/dead.md", "verified_at": "x"},
        {"name": 42, "kind": "script", "defects": ["undocumented"], "doc_link": None},
    ])
    rep2 = aud.run(cj2, apply=True, root=tmp_path)
    assert any("42" in f for f in rep2["fixed"]), rep2["fixed"]
    assert (tmp_path / "docs" / "development" / "capability-defects.md").exists()


# --- Behavior 2: undocumented → stub written + linked; doc_drift → flagged, not silently rewritten ------

def test_undocumented_writes_stub_only_under_apply(tmp_path) -> None:
    cj = _write_catalog(tmp_path, [
        {"name": "fabrik foo", "kind": "cli", "summary": "does foo", "invoke": "python -m x", "status": "ok",
         "defects": ["undocumented"], "doc_link": None, "verified_at": "x"},
    ])
    stub_dir = tmp_path / "docs" / "reference" / "capabilities"
    rep = aud.run(cj, apply=False, root=tmp_path)
    assert not stub_dir.exists() or not list(stub_dir.glob("*.md")), "dry-run must not write a stub"
    assert any("stub" in f.lower() for f in rep["fixed"])
    aud.run(cj, apply=True, root=tmp_path)
    stubs = list((tmp_path / "docs" / "reference" / "capabilities").glob("*.md"))
    assert stubs, "apply must write a stub doc"
    assert "fabrik foo" in stubs[0].read_text()


def test_doc_drift_is_flagged_not_rewritten(tmp_path) -> None:
    doc = tmp_path / "docs" / "drifted.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("original content\n")
    cj = _write_catalog(tmp_path, [
        {"name": "x", "kind": "script", "summary": "", "invoke": "python x", "status": "ok",
         "defects": ["doc_drift"], "doc_link": "docs/drifted.md", "verified_at": "x"},
    ])
    aud.run(cj, apply=True, root=tmp_path)
    assert doc.read_text() == "original content\n", "doc_drift must be flagged, never auto-rewritten"
    report = (tmp_path / "docs" / "development" / "capability-defects.md").read_text()
    assert "drift" in report.lower()


# --- Behavior 3: idempotent — a clean catalog (no defects) → empty ledger + zero file changes -----------

def test_idempotent_on_clean_catalog(tmp_path) -> None:
    cj = _write_catalog(tmp_path, [
        {"name": "x", "kind": "script", "summary": "ok", "invoke": "python x", "status": "ok",
         "defects": [], "doc_link": "INDEX.md", "verified_at": "x"},
    ])
    rep = aud.run(cj, apply=True, root=tmp_path)
    assert rep["fixed"] == [] and rep["operator_action"] == []
    # the report is still written (an empty ledger), but no other file is created/changed
    report = tmp_path / "docs" / "development" / "capability-defects.md"
    assert report.exists()
    created = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert {p.name for p in created} == {"capabilities.json", "capability-defects.md"}


def test_report_always_written_with_full_dry_run_plan(tmp_path) -> None:
    cj = _write_catalog(tmp_path, [
        {"name": "brokentool", "kind": "cli", "summary": "", "invoke": "python x", "status": "broken",
         "defects": ["broken"], "doc_link": "AGENTS.md", "verified_at": "x"},
    ])
    aud.run(cj, apply=False, root=tmp_path)
    report = (tmp_path / "docs" / "development" / "capability-defects.md").read_text()
    assert "brokentool" in report and "broken" in report.lower()
