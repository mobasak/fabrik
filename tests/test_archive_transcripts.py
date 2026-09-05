"""Behavior Contract — Phase A of the session-history retention plan
(`docs/development/plans/2026-09-06-plan-1-session-history-retention.md`).

Every test here guards a way the ARCHIVE could silently fail to be what Phase C will one
day delete against. A manifest row is a promise that the bytes exist; these prove the
promise is only made when it is true.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "sysadmin" / "archive_transcripts.py"

spec = importlib.util.spec_from_file_location("archive_transcripts", SCRIPT)
at = importlib.util.module_from_spec(spec)
spec.loader.exec_module(at)

pytestmark = pytest.mark.skipif(shutil.which("zstd") is None, reason="zstd not installed")


@pytest.fixture
def tree(tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    (projects / "-opt-alpha").mkdir(parents=True)
    (projects / "-opt-beta").mkdir(parents=True)
    # SAME session id under TWO project slugs — the collision the 2-part key could not see
    (projects / "-opt-alpha" / "shared-id.jsonl").write_bytes(b'{"a":1}\n' * 100)
    (projects / "-opt-beta" / "shared-id.jsonl").write_bytes(b'{"b":2}\n' * 200)
    subs = projects / "-opt-alpha" / "shared-id" / "subagents"
    subs.mkdir(parents=True)
    (subs / "agent-x.jsonl").write_bytes(b"S" * 50_000)
    archive = tmp_path / "archive"
    monkeypatch.setenv("CLAUDE_PROJECTS_DIR", str(projects))
    monkeypatch.setenv("ARCHIVE_ROOT", str(archive))
    monkeypatch.delenv("ARCHIVE_MAX_FILE_MB", raising=False)
    return projects, archive


def _rows(archive: Path) -> list[dict]:
    m = archive / at.MANIFEST_NAME
    return [json.loads(x) for x in m.read_text().splitlines()] if m.exists() else []


def test_manifest_sha_matches_the_source_bytes(tree):
    projects, archive = tree
    assert at.run(["--no-ship"]) == 0
    rows = _rows(archive)
    assert rows, "no manifest rows written"
    for r in rows:
        src = projects / r["project_slug"] / f"{r['session_id']}.jsonl"
        assert r["sha256"] == at._sha256(src), "manifest vouches for bytes it did not hash"
        assert r["bytes"] == src.stat().st_size


def test_manifest_key_disambiguates_the_same_session_id_across_projects(tree):
    """`session_id` is unique inside a project dir, NOT across all 266 of them. A
    (session_id, sha256) key — the plan's first draft — could match a transcript against
    another project's archive."""
    _projects, archive = tree
    at.run(["--no-ship"])
    rows = [r for r in _rows(archive) if r["session_id"] == "shared-id"]
    assert len(rows) == 2, "both projects' same-named sessions must be archived"
    assert {r["project_slug"] for r in rows} == {"-opt-alpha", "-opt-beta"}
    assert rows[0]["sha256"] != rows[1]["sha256"], "different content, different digest"
    # and both artifacts exist, under their own slug
    for r in rows:
        assert (archive / r["project_slug"] / f"{r['session_id']}.jsonl.zst").is_file()


def test_subagent_transcripts_never_enter_the_archive(tree):
    """Subagents are a separate tier (7 days, no archive). One leaking in would be archived
    forever and would inflate the store the cap is measured against."""
    _projects, archive = tree
    at.run(["--no-ship"])
    assert all("agent-" not in r["session_id"] for r in _rows(archive))
    assert not list(archive.rglob("agent-*.zst"))


def test_file_over_the_ceiling_is_reported_not_archived(tree, monkeypatch, capsys):
    """The aggregate bound is blind to a runaway session — the largest real transcript is
    733,603,901 bytes. An over-ceiling file must be REPORTED, never silently archived."""
    _projects, archive = tree
    # A ceiling BETWEEN the two fixtures (alpha 800 B, beta 1600 B): 1048 B. This proves the
    # ceiling is SELECTIVE — the under-ceiling file still archives — which an all-exceed
    # ceiling could not distinguish from the archiver simply refusing everything.
    monkeypatch.setenv("ARCHIVE_MAX_FILE_MB", "0.001")  # 0.001 MiB = 1048 bytes
    assert at.run(["--no-ship"]) == 0
    out = capsys.readouterr().out
    assert "OVER-CEILING" in out, out
    rows = _rows(archive)
    slugs = {r["project_slug"] for r in rows}
    assert slugs == {"-opt-alpha"}, f"only the under-ceiling file may be archived; got {slugs}"
    assert not (archive / "-opt-beta" / "shared-id.jsonl.zst").exists(), (
        "the over-ceiling file was archived anyway"
    )


def test_transport_failure_writes_no_manifest_rows(tree, monkeypatch):
    """THE ORDERING INVARIANT. A manifest row is what Phase C will accept as permission to
    delete a local file, so it must never exist for bytes that did not land remotely."""
    _projects, archive = tree

    def boom(*_a, **_kw):
        raise subprocess.CalledProcessError(1, "rsync")

    monkeypatch.setattr(at, "ship", boom)
    assert at.run([]) == 1, "transport failure must exit non-zero"
    assert _rows(archive) == [], "manifest rows were written despite a failed transport"


def test_transport_never_carries_a_deleting_flag():
    """`--delete` / `--remove-source-files` turn rsync into a mirror that would delete the
    ARCHIVE when the local side is pruned, inverting the whole safety model.

    ⚠️ This reads the rsync ARGUMENT LIST via the AST, not the source text. The module
    docstring deliberately NAMES both flags to explain the ban, so a grep-based guard would
    fail on its own documentation — and, worse, would tempt someone to delete the
    explanation to make the test pass."""
    tree_ = ast.parse(SCRIPT.read_text())
    rsync_calls = []
    for node in ast.walk(tree_):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.List) and first.elts:
            head = first.elts[0]
            if isinstance(head, ast.Constant) and head.value == "rsync":
                rsync_calls.append([getattr(e, "value", None) for e in first.elts])
    assert rsync_calls, "no rsync invocation found — has the transport moved?"
    for argv in rsync_calls:
        assert "--delete" not in argv, f"BANNED --delete in transport: {argv}"
        assert "--remove-source-files" not in argv, f"BANNED --remove-source-files: {argv}"
        assert "-z" not in argv, "-z re-compresses an already-zstd payload every run"
