"""Tier-D per-project system prompt: the driver reads a project-relative Markdown
file into WATCHDOG_SYSTEM_PROMPT, FAIL-SOFT (never raises, never reads a bad path,
never disables the watchdog) on any misconfiguration.

Covers the security path (traversal / symlink / absolute / poisoned id) + the
fail-soft contract (missing / non-file / non-UTF-8 / null-byte / oversized / non-str
→ "" + a logged warning) + the happy path and the exact size boundary.
"""

import logging
import os

import pytest

from fabrik.drivers import watchdog as wd


@pytest.fixture()
def project(tmp_path, monkeypatch):
    """A fake /opt/<id> project dir; point the driver's projects-root at it."""
    monkeypatch.setattr(wd, "_PROJECTS_ROOT", tmp_path)
    pid = "calendar-orchestration-engine"
    pdir = tmp_path / pid
    (pdir / "docs").mkdir(parents=True)
    return pid, pdir


def _f(pid, path):
    return wd._load_project_prompt({"project_system_prompt_file": path}, pid)


# ── unset / happy / boundary ────────────────────────────────────────────────
def test_unset_returns_empty(project):
    pid, _ = project
    assert wd._load_project_prompt({}, pid) == ""
    assert wd._load_project_prompt({"project_system_prompt_file": ""}, pid) == ""
    assert wd._load_project_prompt({"project_system_prompt_file": None}, pid) == ""


def test_reads_file_contents(project):
    pid, pdir = project
    body = "# Calendar\n\nHealthy = /api/health 200 + poll worker alive.\n"
    (pdir / "docs" / "WATCHDOG_PROMPT.md").write_text(body, encoding="utf-8")
    assert _f(pid, "docs/WATCHDOG_PROMPT.md") == body


def test_exact_boundary_accepted(project):
    """A file of EXACTLY _MAX_PROMPT_BYTES is accepted (guards > vs >=)."""
    pid, pdir = project
    body = "x" * wd._MAX_PROMPT_BYTES
    (pdir / "docs" / "WATCHDOG_PROMPT.md").write_text(body, encoding="utf-8")
    assert _f(pid, "docs/WATCHDOG_PROMPT.md") == body


def test_multibyte_size_uses_bytes_not_chars(project):
    """Size is measured in bytes, so a small char-count but >MAX-byte file is rejected."""
    pid, pdir = project
    # '€' is 3 UTF-8 bytes; (MAX//3 + 1) chars => > MAX bytes but far fewer chars.
    body = "€" * (wd._MAX_PROMPT_BYTES // 3 + 1)
    (pdir / "docs" / "P.md").write_text(body, encoding="utf-8")
    assert _f(pid, "docs/P.md") == ""


# ── fail-soft: every bad input → "" + a logged warning, never an exception ──
def _assert_soft(project, path, caplog, match):
    pid, _ = project
    with caplog.at_level(logging.WARNING):
        out = _f(pid, path)
    assert out == ""
    assert any(match in r.getMessage() for r in caplog.records), caplog.text


def test_missing_file_soft(project, caplog):
    _assert_soft(project, "docs/WATCHDOG_PROMPT.md", caplog, "not found")


def test_absolute_path_soft(project, caplog):
    _assert_soft(project, "/etc/passwd", caplog, "project-relative")


def test_traversal_soft_does_not_read(project, caplog):
    """A '..' escape returns "" and NEVER reads the outside file."""
    pid, _ = project
    (wd._PROJECTS_ROOT / "secret.md").write_text("TOP-SECRET", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        out = _f(pid, "../secret.md")
    assert out == ""
    assert "TOP-SECRET" not in out
    assert any("outside the project dir" in r.getMessage() for r in caplog.records)


def test_symlink_escape_soft(project, caplog):
    """An in-project symlink pointing outside resolves out → refused, not read."""
    pid, pdir = project
    outside = wd._PROJECTS_ROOT / "outside.md"
    outside.write_text("LEAK", encoding="utf-8")
    link = pdir / "docs" / "link.md"
    os.symlink(outside, link)
    with caplog.at_level(logging.WARNING):
        out = _f(pid, "docs/link.md")
    assert out == "" and "LEAK" not in out
    assert any("outside the project dir" in r.getMessage() for r in caplog.records)


def test_directory_target_soft(project, caplog):
    _assert_soft(project, "docs", caplog, "not found")


def test_oversized_soft(project, caplog):
    pid, pdir = project
    (pdir / "docs" / "P.md").write_text("x" * (wd._MAX_PROMPT_BYTES + 1), encoding="utf-8")
    _assert_soft(project, "docs/P.md", caplog, "too large")


def test_null_byte_soft(project, caplog):
    _assert_soft(project, "docs/x\x00.md", caplog, "could not read")


def test_non_utf8_file_soft(project, caplog):
    pid, pdir = project
    (pdir / "docs" / "P.md").write_bytes(b"\xff\xfe\x00\x01 not utf-8")
    _assert_soft(project, "docs/P.md", caplog, "could not read")


def test_poisoned_project_id_soft(project, caplog):
    """An unsafe id ('..' / '/' / leading '.') is refused with a warning."""
    pid, _ = project
    for bad_id in ("../evil", "a/b", "..", ".hidden"):
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            out = wd._load_project_prompt(
                {"project_system_prompt_file": "docs/WATCHDOG_PROMPT.md"}, bad_id
            )
        assert out == ""
        assert any("unsafe project id" in r.getMessage() for r in caplog.records), bad_id


def test_symlink_loop_soft(project, caplog):
    """A symlink loop inside the project degrades to '' (no crash)."""
    pid, pdir = project
    a, b = pdir / "docs" / "a.md", pdir / "docs" / "b.md"
    os.symlink(b, a)
    os.symlink(a, b)
    with caplog.at_level(logging.WARNING):
        assert _f(pid, "docs/a.md") == ""
    # Pin to this function's fail-soft signature (all its warnings end "... prompt"),
    # robust to the loop surfacing as either "not found" or "could not read".
    assert any("canonical prompt" in r.getMessage() for r in caplog.records)


def test_non_str_rel_soft(project, caplog):
    pid, _ = project
    for bad in (123, True, ["docs/x.md"], {"a": 1}):
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            out = wd._load_project_prompt({"project_system_prompt_file": bad}, pid)
        assert out == ""
        assert any("must be a string" in r.getMessage() for r in caplog.records), bad


@pytest.mark.parametrize(
    "bad",
    ["/etc/passwd", "../secret.md", "docs/x\x00.md", "docs", "missing.md", 42, True],
)
def test_never_raises(project, bad):
    """The fail-soft contract: no input path ever raises out of the loader."""
    pid, _ = project
    assert wd._load_project_prompt({"project_system_prompt_file": bad}, pid) == ""
