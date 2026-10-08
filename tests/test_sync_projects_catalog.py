"""Catalog edge cases in scripts/sync_projects.py (W-34d48ecb review, mail 01M49YA501).

The module is loaded by path from THIS checkout: a package import can resolve to the main
checkout's copy from a worktree, and then these tests grade the wrong file.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def sync():
    spec = importlib.util.spec_from_file_location(
        "sync_projects_under_test", ROOT / "scripts" / "sync_projects.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _project(tmp_path: Path, yaml_text: str) -> Path:
    p = tmp_path / "demo"
    p.mkdir()
    (p / "project.yaml").write_text(yaml_text, encoding="utf-8")
    return p


def test_a_null_category_is_auto_categorized_not_left_at_the_default(sync, tmp_path):
    # `category:` with no value used to count as explicit, so the project kept the dataclass
    # default "planning" instead of what auto-detection decides for the same folder.
    path = _project(tmp_path, "category:\n")
    project = sync._build_project(path)
    assert project.category == sync._auto_categorize(path, project.status)


def test_a_scalar_project_yaml_does_not_abort_the_scan(sync, tmp_path):
    # `42` made `"category" in pdata` raise TypeError, which aborted the whole /opt scan.
    path = _project(tmp_path, "42\n")
    project = sync._build_project(path)
    assert project.category == sync._auto_categorize(path, project.status)


def test_a_list_category_renders_under_other_and_keeps_total_equal_to_rows(sync, tmp_path):
    # An unhashable category used to raise in the catch-all set membership.
    project = sync._build_project(_project(tmp_path, "category: [services, api]\n"))
    md = sync.generate_catalog_markdown([project])
    assert "<!-- Total projects: 1 -->" in md
    assert "### Other" in md
    assert md.count("| **demo** |") == 1


def test_a_pipe_in_a_cell_does_not_add_columns(sync):
    project = sync.Project(name="demo", path="/x", description="Proxy | Broker", category="active")
    row = next(
        line
        for line in sync.generate_catalog_markdown([project]).splitlines()
        if "**demo**" in line
    )
    unescaped = row.replace("\\|", "")
    assert unescaped.count("|") == 7  # six cells
    assert "Proxy \\| Broker" in row


def test_a_url_that_is_not_a_link_renders_as_a_dash(sync):
    # /opt/proxy/project.yaml sets `url: Multi-service proxy broker`, and the URL column
    # showed the sentence until this fix.
    text = sync.Project(name="demo", path="/x", url="Multi-service proxy broker", category="active")
    link = sync.Project(
        name="link", path="/y", url="https://link.vps1.ocoron.com", category="active"
    )
    md = sync.generate_catalog_markdown([text, link])
    demo = next(line for line in md.splitlines() if "**demo**" in line)
    assert "Multi-service proxy broker" not in demo and "| - |" in demo
    assert "https://link.vps1.ocoron.com" in md
