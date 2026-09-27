"""A project's PORTS.md is the hub's port registry, never a per-project file (D-380).

The governance sync distributes the hub's PORTS.md and gitignores it in every project, so a
per-project file the scaffolder wrote there was replaced by the first forced sync with no git
trace. The scaffolder now leaves the hub copy it seeds in place.
"""

from __future__ import annotations

import logging

import fabrik.scaffold as scaffold


def test_a_new_project_holds_the_hub_port_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("FABRIK_SCAFFOLD_OFFLINE", "1")
    hub = scaffold.HUB_PORTS_MD
    assert hub.exists(), "the hub has no PORTS.md — the comparison would be vacuous"

    scaffold.create_project(
        name="ports-probe",
        description="d",
        base=tmp_path,
        project_type="python-api",
        generate_spec=False,
    )

    assert (tmp_path / "ports-probe" / "PORTS.md").read_bytes() == hub.read_bytes()


def test_a_missing_hub_registry_is_said_not_swallowed(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("FABRIK_SCAFFOLD_OFFLINE", "1")
    monkeypatch.setattr(scaffold, "HUB_PORTS_MD", tmp_path / "absent" / "PORTS.md")

    with caplog.at_level(logging.WARNING, logger=scaffold.logger.name):
        scaffold.create_project(
            name="noports",
            description="d",
            base=tmp_path,
            project_type="python-api",
            generate_spec=False,
        )

    assert not (tmp_path / "noports" / "PORTS.md").exists()
    assert any("port registry" in r.getMessage() for r in caplog.records)
