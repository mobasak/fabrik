"""T04 (Coolify-verb retirement, D4) — `fabrik projects --sync` re-scans `/opt` first.

`--sync` runs the project scanner as the same subprocess `fabrik scan` runs
(`cli.py` — the `["python3", str(sync_script)]` argv, `cwd=FABRIK_ROOT`) BEFORE
`ProjectRegistry()` is constructed, because the scanner rewrites `data/projects.yaml`,
the file the registry's `__init__` loads. `subprocess.run` is faked here — never the
real scanner. The Coolify sync block is gone: no Coolify API client, no
`registry.update(..., coolify_uuid=..., coolify_name=...)`, no `coolify_uuid`/
`coolify_name` fields on `Project`.
"""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

import fabrik.cli as cli_module
import fabrik.registry as registry_module

cli = cli_module.cli


def _write_registry(path: Path, projects: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump(
            {"version": 1, "last_scan": None, "exclude": [], "projects": projects},
            default_flow_style=False,
            sort_keys=False,
        )
    )


@pytest.fixture
def fabrik_root(tmp_path, monkeypatch):
    """Point both `cli.py`'s and `registry.py`'s module-level `FABRIK_ROOT` at a
    throwaway tree, and plant a stub `scripts/sync_projects.py` so the existence
    check inside `projects` passes without ever running the real scanner
    (`subprocess.run` itself is faked in every test below)."""
    root = tmp_path / "root"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "sync_projects.py").write_text("# stub for the exists() check\n")
    monkeypatch.setattr(cli_module, "FABRIK_ROOT", root)
    monkeypatch.setattr(registry_module, "FABRIK_ROOT", root)
    return root


class TestSyncReadsRegistryAfterSubprocess:
    def test_sync_runs_the_scan_argv_then_lists_the_project_it_wrote(self, fabrik_root):
        registry_path = fabrik_root / "data" / "projects.yaml"
        _write_registry(
            registry_path,
            {
                "old-proj": {
                    "path": "/opt/old-proj",
                    "type": "service",
                    "status": "ready",
                    "has_user_guide": False,
                }
            },
        )
        sync_script = fabrik_root / "scripts" / "sync_projects.py"
        calls: list[tuple[list[str], dict]] = []

        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            # Prove the registry is read AFTER this returns: rewrite the file the
            # way the real scanner would, adding a project that was NOT there
            # before this fake ran.
            _write_registry(
                registry_path,
                {
                    "old-proj": {
                        "path": "/opt/old-proj",
                        "type": "service",
                        "status": "ready",
                        "has_user_guide": False,
                    },
                    "new-proj": {
                        "path": "/opt/new-proj",
                        "type": "service",
                        "status": "ready",
                        "has_user_guide": False,
                    },
                },
            )
            return subprocess.CompletedProcess(argv, 0)

        with patch("subprocess.run", side_effect=fake_run) as fake:
            result = CliRunner().invoke(cli, ["projects", "--sync"])

        assert result.exit_code == 0, result.output
        assert fake.call_count == 1
        argv, kwargs = calls[0]
        assert argv == ["python3", str(sync_script)]
        assert kwargs.get("cwd") == str(fabrik_root)
        assert "new-proj" in result.output
        assert "old-proj" in result.output

    def test_sync_script_missing_exits_before_any_subprocess_call(self, fabrik_root):
        # Remove the stub the fixture planted — the exists() guard must fire first.
        (fabrik_root / "scripts" / "sync_projects.py").unlink()

        with patch("subprocess.run") as fake:
            result = CliRunner().invoke(cli, ["projects", "--sync"])

        assert result.exit_code == 1, result.output
        assert "sync_projects.py not found" in result.output
        assert "PROJECT" not in result.output
        fake.assert_not_called()

    def test_sync_scanner_failure_propagates_rc_and_prints_no_listing(self, fabrik_root):
        """A scanner that exits non-zero ends the verb with ITS code and no stale listing follows."""
        _write_registry(
            fabrik_root / "data" / "projects.yaml",
            {
                "stale-proj": {
                    "path": "/opt/stale-proj",
                    "type": "service",
                    "status": "development",
                    "has_user_guide": False,
                }
            },
        )
        with patch(
            "subprocess.run", return_value=subprocess.CompletedProcess(["python3"], 3)
        ) as fake:
            result = CliRunner().invoke(cli, ["projects", "--sync"])
        assert fake.call_count == 1
        assert result.exit_code == 3, result.output
        assert "PROJECT" not in result.output
        assert "stale-proj" not in result.output


class TestHelpText:
    def test_sync_help_reads_rescan_and_merge(self):
        result = CliRunner().invoke(cli, ["projects", "--help"])
        assert result.exit_code == 0
        assert "Re-scan /opt and merge the deploy state before listing" in result.output

    def test_status_help_names_both_registry_vocabularies_never_deployed(self):
        """scan writes ready/development; --sync (scripts/sync_projects.py) writes the other four."""
        result = CliRunner().invoke(cli, ["projects", "--help"])
        assert result.exit_code == 0
        flat = " ".join(result.output.split())
        assert "ready/development after `fabrik scan`" in flat
        assert "production/development/archived/paused after --sync" in flat
        assert "deployed" not in result.output


class TestRegistryDropsCoolifyFields:
    def test_row_with_coolify_keys_loads_its_other_fields_unchanged(self, tmp_path):
        registry_path = tmp_path / "projects.yaml"
        _write_registry(
            registry_path,
            {
                "legacy-proj": {
                    "path": "/opt/legacy-proj",
                    "type": "service",
                    "status": "ready",
                    "coolify_uuid": "abc-123",
                    "coolify_name": "fabrik-legacy-proj",
                    "domain": "legacy.example.com",
                    "port": 8080,
                    "has_user_guide": True,
                }
            },
        )

        reg = registry_module.ProjectRegistry(path=registry_path)
        p = reg.get("legacy-proj")

        assert p is not None
        assert not hasattr(p, "coolify_uuid")
        assert not hasattr(p, "coolify_name")
        assert p.path == "/opt/legacy-proj"
        assert p.type == "service"
        assert p.status == "ready"
        assert p.domain == "legacy.example.com"
        assert p.port == 8080
        assert p.has_user_guide is True

        d = p.to_dict()
        assert "coolify_uuid" not in d
        assert "coolify_name" not in d


class TestNoCoolifyWord:
    def test_rebased_projects_names_neither_coolify_nor_registry_update(self):
        src = inspect.getsource(cli_module.projects.callback)
        assert "coolify" not in src.lower()
        assert "registry.update" not in src

    def test_registry_update_called_nowhere_in_cli_py(self):
        cli_source = Path(cli_module.__file__).read_text()
        assert "registry.update(" not in cli_source
