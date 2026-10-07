"""Tests for T2-04 G-J1: sync_projects.py state-file merge.

Covers ``_load_deploy_state(project_name)``:
- Returns ``last_apply_status: never`` when no state file exists
- Returns deploy fields when state file exists at .fabrik/state/<id>.json
- Falls back to fabrik-<id>.json if the bare id has no file
- Handles malformed state files gracefully
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _isolate_fabrik_root(tmp_path, monkeypatch):
    """Point FABRIK_ROOT at a tmp dir so tests don't pollute the live state."""
    fake_root = tmp_path / "fabrik"
    fake_root.mkdir()
    (fake_root / ".fabrik" / "state").mkdir(parents=True)
    monkeypatch.setattr("scripts.sync_projects.FABRIK_ROOT", fake_root)
    yield fake_root


def _import_sync(fake_root=None):
    # Add scripts/ to sys.path so the bare module name works
    import sys

    scripts = "/opt/fabrik/scripts"
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import scripts.sync_projects as sync  # type: ignore[import-not-found]

    return sync


# ─────────────────────────────────────────────────────────────────────────────
# _load_deploy_state
# ─────────────────────────────────────────────────────────────────────────────


def test_no_state_file_returns_never(_isolate_fabrik_root):
    sync = _import_sync()
    sync.FABRIK_ROOT = _isolate_fabrik_root  # noqa: SLF001
    r = sync._load_deploy_state("nonexistent-project")
    assert r == {"last_apply_status": "never"}


def test_state_file_returns_applied_fields(_isolate_fabrik_root):
    sync = _import_sync()
    sync.FABRIK_ROOT = _isolate_fabrik_root  # noqa: SLF001
    state_path = _isolate_fabrik_root / ".fabrik" / "state" / "translator.json"
    state_path.write_text(
        json.dumps(
            {
                "applied_at": "2026-05-15T22:00:00+00:00",
                "coolify_app_name": "fabrik-translator",
                "coolify_uuid": "kgws0s4cscsosw8gg848cwgw",
                "domain": "translator.vps1.ocoron.com",
                "git_sha": "abc123",
                "registrars_applied": [
                    {
                        "type": "postgres",
                        "id": "translator",
                        "status": "applied",
                        "data_bearing": True,
                    },
                    {
                        "type": "gatus",
                        "id": "translator",
                        "status": "applied",
                        "data_bearing": False,
                    },
                ],
                "spec_hash": "deadbeef0000abcd",
                "spec_path": "/opt/fabrik/specs/services/translator.yaml",
            }
        )
    )

    r = sync._load_deploy_state("translator")
    assert r["last_apply_status"] == "applied"
    assert r["last_apply_at"] == "2026-05-15T22:00:00+00:00"
    assert r["last_apply_sha"] == "abc123"
    assert r["coolify_uuid"] == "kgws0s4cscsosw8gg848cwgw"
    assert r["coolify_app_name"] == "fabrik-translator"
    assert r["spec_path"] == "/opt/fabrik/specs/services/translator.yaml"
    assert sorted(r["registrars_applied"]) == ["gatus", "postgres"]
    # a file written before registrar_failures existed records none
    assert r["registrar_failures"] == []


def test_recorded_registrar_failures_mark_the_apply(_isolate_fabrik_root):
    """projects.yaml must not say "applied" for an apply whose registrars failed (W-2013a22d)."""
    sync = _import_sync()
    sync.FABRIK_ROOT = _isolate_fabrik_root  # noqa: SLF001
    failures = [{"registrar": "redis", "error": "REDIS_URL injection failed"}]
    (_isolate_fabrik_root / ".fabrik" / "state" / "svc.json").write_text(
        json.dumps(
            {
                "applied_at": "2026-10-07T00:00:00+00:00",
                "registrars_applied": [],
                "registrar_failures": failures,
            }
        )
    )
    r = sync._load_deploy_state("svc")
    assert r["last_apply_status"] == "applied_with_failures"
    assert r["registrar_failures"] == failures


def test_fabrik_prefix_fallback(_isolate_fabrik_root):
    """If state/<id>.json missing, try state/fabrik-<id>.json."""
    sync = _import_sync()
    sync.FABRIK_ROOT = _isolate_fabrik_root  # noqa: SLF001
    state_path = _isolate_fabrik_root / ".fabrik" / "state" / "fabrik-myapp.json"
    state_path.write_text(
        json.dumps(
            {
                "applied_at": "2026-05-15T22:00:00+00:00",
                "coolify_app_name": "fabrik-myapp",
                "coolify_uuid": "abc",
                "domain": "myapp.example.com",
                "git_sha": "",
                "registrars_applied": [],
                "spec_hash": "",
                "spec_path": "/x.yaml",
            }
        )
    )

    r = sync._load_deploy_state("myapp")
    assert r["last_apply_status"] == "applied"
    assert r["coolify_app_name"] == "fabrik-myapp"


def test_malformed_state_returns_unknown(_isolate_fabrik_root):
    sync = _import_sync()
    sync.FABRIK_ROOT = _isolate_fabrik_root  # noqa: SLF001
    state_path = _isolate_fabrik_root / ".fabrik" / "state" / "broken.json"
    state_path.write_text("not valid json {")

    r = sync._load_deploy_state("broken")
    assert r["last_apply_status"] == "unknown"
    assert "error" in r


def test_registrars_applied_filters_non_dict_entries(_isolate_fabrik_root):
    sync = _import_sync()
    sync.FABRIK_ROOT = _isolate_fabrik_root  # noqa: SLF001
    state_path = _isolate_fabrik_root / ".fabrik" / "state" / "mixed.json"
    state_path.write_text(
        json.dumps(
            {
                "applied_at": "",
                "coolify_app_name": "mixed",
                "coolify_uuid": None,
                "domain": "",
                "git_sha": "",
                "registrars_applied": [
                    {"type": "postgres"},
                    None,  # malformed entry
                    "not a dict",  # malformed entry
                    {"id": "no-type-key"},  # missing 'type'
                    {"type": "gatus"},
                ],
                "spec_hash": "",
                "spec_path": "",
            }
        )
    )

    r = sync._load_deploy_state("mixed")
    assert sorted(r["registrars_applied"]) == ["gatus", "postgres"]


# ─────────────────────────────────────────────────────────────────────────────
# Project dataclass + to_registry_dict
# ─────────────────────────────────────────────────────────────────────────────


def test_project_emits_deploy_block_when_populated(_isolate_fabrik_root):
    sync = _import_sync()
    sync.FABRIK_ROOT = _isolate_fabrik_root  # noqa: SLF001
    p = sync.Project(
        name="x",
        path="/opt/x",
        deploy={"last_apply_status": "applied", "coolify_uuid": "abc"},
    )
    d = p.to_registry_dict()
    assert "deploy" in d
    assert d["deploy"]["last_apply_status"] == "applied"


def test_project_omits_empty_deploy_block(_isolate_fabrik_root):
    sync = _import_sync()
    p = sync.Project(name="x", path="/opt/x")  # deploy defaults to {}
    d = p.to_registry_dict()
    assert "deploy" not in d


# ─────────────────────────────────────────────────────────────────────────────
# Primary path: full apply → state → projects.yaml roundtrip (SC-2)
# ─────────────────────────────────────────────────────────────────────────────


def test_apply_state_to_projects_yaml_roundtrip(_isolate_fabrik_root):
    """Write a state file, run _load_deploy_state, embed into a Project,
    serialize via to_registry_dict — verify all 7 deploy fields round-trip."""
    sync = _import_sync()
    sync.FABRIK_ROOT = _isolate_fabrik_root  # noqa: SLF001

    # 1. Simulate fabrik apply success: write state file
    state_path = _isolate_fabrik_root / ".fabrik" / "state" / "roundtrip-svc.json"
    state_path.write_text(
        json.dumps(
            {
                "applied_at": "2026-05-15T22:00:00+00:00",
                "coolify_app_name": "fabrik-roundtrip-svc",
                "coolify_uuid": "uuid24characters12345678",
                "domain": "roundtrip.example.com",
                "git_sha": "deadbeef1234567890abcdef",
                "registrars_applied": [
                    {
                        "type": "postgres",
                        "id": "roundtrip-svc",
                        "status": "applied",
                        "data_bearing": True,
                    },
                    {
                        "type": "gatus",
                        "id": "roundtrip-svc",
                        "status": "applied",
                        "data_bearing": False,
                    },
                    {
                        "type": "authelia",
                        "id": "roundtrip.example.com",
                        "status": "applied",
                        "data_bearing": False,
                    },
                ],
                "spec_hash": "1234567890abcdef",
                "spec_path": "/opt/fabrik/specs/services/roundtrip-svc.yaml",
            }
        )
    )

    # 2. sync_projects loads state into Project.deploy
    deploy = sync._load_deploy_state("roundtrip-svc")
    project = sync.Project(name="roundtrip-svc", path="/opt/roundtrip-svc", deploy=deploy)

    # 3. to_registry_dict serializes for yaml output
    d = project.to_registry_dict()
    assert d["deploy"]["last_apply_status"] == "applied"
    assert d["deploy"]["last_apply_sha"] == "deadbeef1234567890abcdef"
    assert d["deploy"]["coolify_uuid"] == "uuid24characters12345678"
    assert d["deploy"]["coolify_app_name"] == "fabrik-roundtrip-svc"
    assert sorted(d["deploy"]["registrars_applied"]) == ["authelia", "gatus", "postgres"]
    assert d["deploy"]["spec_path"] == "/opt/fabrik/specs/services/roundtrip-svc.yaml"


# ─────────────────────────────────────────────────────────────────────────────
# _check_scaffold — the scaffold marker after `.windsurfrules` is retired (D-529)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("files", "symlink", "expected"),
    [
        (("AGENTS.md", "project.yaml"), False, "current"),
        (("AGENTS.md",), False, "no-project-yaml"),
        (("project.yaml",), False, "missing"),
        (("AGENTS.md", "project.yaml"), True, "stale-symlink"),
    ],
    ids=["current", "no-project-yaml", "missing", "stale-symlink"],
)
def test_the_scaffold_marker_is_the_synced_agents_md(tmp_path, files, symlink, expected):
    """The sync prunes `.windsurfrules` from every project, so a marker keyed on it would read
    every pruned project as "No scaffold". AGENTS.md is synced to every project instead."""
    sync = _import_sync()
    proj = tmp_path / "proj"
    proj.mkdir()
    for name in files:
        if name == "AGENTS.md" and symlink:
            target = tmp_path / "hub-AGENTS.md"
            target.write_text("hub\n")
            (proj / name).symlink_to(target)
        else:
            (proj / name).write_text("x\n")
    assert sync._check_scaffold(proj) == expected
