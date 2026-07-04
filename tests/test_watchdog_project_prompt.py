"""Tier-D per-project system prompt: driver reads a project-relative Markdown file
into WATCHDOG_SYSTEM_PROMPT, fail-closed on a misconfigured path.

Covers the highest-risk path (path-traversal / fail-closed) + the happy/empty paths.
"""

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


def test_unset_returns_empty(project):
    pid, _ = project
    assert wd._load_project_prompt({}, pid) == ""
    assert wd._load_project_prompt({"project_system_prompt_file": ""}, pid) == ""


def test_reads_file_contents(project):
    pid, pdir = project
    body = "# Calendar\n\nHealthy = /api/health 200 + poll worker alive.\n"
    (pdir / "docs" / "WATCHDOG_PROMPT.md").write_text(body, encoding="utf-8")
    got = wd._load_project_prompt(
        {"project_system_prompt_file": "docs/WATCHDOG_PROMPT.md"}, pid
    )
    assert got == body


def test_missing_file_fails_closed(project):
    pid, _ = project
    with pytest.raises(wd.WatchdogProvisionError, match="not found"):
        wd._load_project_prompt(
            {"project_system_prompt_file": "docs/WATCHDOG_PROMPT.md"}, pid
        )


def test_absolute_path_refused(project):
    pid, _ = project
    with pytest.raises(wd.WatchdogProvisionError, match="project-relative"):
        wd._load_project_prompt(
            {"project_system_prompt_file": "/etc/passwd"}, pid
        )


def test_traversal_refused(project):
    """A '..' escape must not read outside the project dir even if the target exists."""
    pid, _ = project
    # create a file in the parent (sibling of the project dir) the traversal targets
    (wd._PROJECTS_ROOT / "secret.md").write_text("nope", encoding="utf-8")
    with pytest.raises(wd.WatchdogProvisionError, match="traversal"):
        wd._load_project_prompt(
            {"project_system_prompt_file": "../secret.md"}, pid
        )


def test_oversized_refused(project):
    pid, pdir = project
    (pdir / "docs" / "WATCHDOG_PROMPT.md").write_text(
        "x" * (wd._MAX_PROMPT_BYTES + 1), encoding="utf-8"
    )
    with pytest.raises(wd.WatchdogProvisionError, match="too large"):
        wd._load_project_prompt(
            {"project_system_prompt_file": "docs/WATCHDOG_PROMPT.md"}, pid
        )
