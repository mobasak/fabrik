"""T05 (Coolify-verb retirement, D1) — `fabrik apply` loses its legacy escape hatch.

`--legacy`, the hidden no-op `--use-orchestrator`, `--skip-dns` and `--skip-deploy` are
removed from `fabrik apply` along with the legacy fall-through (everything after the
`if not legacy:` block, which always exited); the orchestrator pipeline is now the only
path. `--yes` stays as a stated no-op ("accepted for compatibility; the orchestrator path
never prompts"). `src/fabrik/deploy.py` (the legacy `deploy_to_coolify` stub) is deleted.
D10's wording pass drops every remaining "Coolify" mention from `cli.py` outside the
`export`/`import` docstring (T06's territory).
"""

from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

import fabrik.cli as cli_module
from fabrik.orchestrator import DeploymentState
from fabrik.orchestrator.context import DeploymentContext

cli = cli_module.cli

REPO_ROOT = Path(__file__).resolve().parent.parent


def _write_spec(tmp_path, name="demo") -> str:
    path = tmp_path / f"{name}.yaml"
    path.write_text(f"id: {name}\ntemplate: python-api\ndomain: {name}.example.com\n")
    return str(path)


class TestRetiredFlagsRefused:
    """Behavior row 1: each retired flag exits 2 with click's own refusal."""

    def test_legacy_flag_refused(self, tmp_path):
        spec_path = _write_spec(tmp_path)
        result = CliRunner().invoke(cli, ["apply", spec_path, "--legacy"])
        assert result.exit_code == 2
        assert "No such option" in result.output
        assert "--legacy" in result.output

    def test_use_orchestrator_flag_refused(self, tmp_path):
        spec_path = _write_spec(tmp_path)
        result = CliRunner().invoke(cli, ["apply", spec_path, "--use-orchestrator"])
        assert result.exit_code == 2
        assert "No such option" in result.output
        assert "--use-orchestrator" in result.output

    def test_skip_dns_flag_refused(self, tmp_path):
        spec_path = _write_spec(tmp_path)
        result = CliRunner().invoke(cli, ["apply", spec_path, "--skip-dns"])
        assert result.exit_code == 2
        assert "No such option" in result.output
        assert "--skip-dns" in result.output

    def test_skip_deploy_flag_refused(self, tmp_path):
        spec_path = _write_spec(tmp_path)
        result = CliRunner().invoke(cli, ["apply", spec_path, "--skip-deploy"])
        assert result.exit_code == 2
        assert "No such option" in result.output
        assert "--skip-deploy" in result.output


class TestYesStaysANoOp:
    """Behavior row 2: --yes is accepted, never prompts, fake orchestrator called once."""

    def test_yes_and_dry_run_call_orchestrator_once_and_never_prompt(self, tmp_path):
        spec_path = _write_spec(tmp_path)

        calls: list[tuple] = []

        class _FakeOrchestrator:
            def __init__(self, *a, **k):
                pass

            def deploy(self, *args, **kwargs):
                calls.append((args, kwargs))
                return DeploymentContext(
                    spec_path=Path(spec_path),
                    spec={"domain": "demo.example.com"},
                    state=DeploymentState.COMPLETE,
                    deployed_url="https://demo.example.com",
                )

        with patch.object(cli_module, "DeploymentOrchestrator", _FakeOrchestrator):
            with patch.object(cli_module, "_post_deploy_sync", lambda: None):
                # CliRunner's default stdin raises on any read — a prompt would fail the
                # run, so a clean exit 0 here is itself proof nothing prompted.
                result = CliRunner().invoke(cli, ["apply", spec_path, "--yes", "--dry-run"])

        assert result.exit_code == 0, result.output
        assert len(calls) == 1

    def test_help_carries_the_compatibility_wording(self):
        result = CliRunner().invoke(cli, ["apply", "--help"])
        assert result.exit_code == 0
        # click wraps long option help across lines at terminal width — normalize
        # whitespace before matching the phrase so a wrap point can't break it.
        normalized = " ".join(result.output.split())
        assert "accepted for compatibility; the orchestrator path never prompts" in normalized


class TestLegacyPathRemoved:
    """Behavior row 3: deploy.py is gone, no importer remains, apply's callback is clean."""

    def test_deploy_py_is_absent(self):
        assert not (REPO_ROOT / "src" / "fabrik" / "deploy.py").exists()

    def test_git_grep_deploy_to_coolify_under_src_is_empty(self):
        result = subprocess.run(
            ["git", "grep", "-n", "deploy_to_coolify", "--", "src"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        # git grep exits 1 when no match is found, 0 when it finds one.
        assert result.returncode == 1, result.stdout
        assert result.stdout == ""

    def test_apply_callback_source_has_no_legacy_or_use_orchestrator(self):
        src = inspect.getsource(cli_module.apply.callback)
        assert "legacy" not in src
        assert "use_orchestrator" not in src


class TestDestroyPreviewAndPartialHelpWordingDroppedCoolify:
    """Behavior row 4: the destroy preview + --partial help no longer say Coolify."""

    def test_partial_help_says_no_dns_removal_no_file_cleanup(self):
        result = CliRunner().invoke(cli, ["destroy", "--help"])
        assert result.exit_code == 0
        # click wraps long option help across lines at terminal width — normalize
        # whitespace before matching the phrase so a wrap point can't break it.
        normalized = " ".join(result.output.split())
        assert "no DNS removal, no file cleanup" in normalized
        assert "coolify" not in result.output.lower()

    def test_destroy_callback_source_has_no_coolify_word(self):
        src = inspect.getsource(cli_module.destroy.callback)
        assert "coolify" not in src.lower()


class TestOnlyRemainingCoolifyHitIsExportImportDocstring:
    """Behavior row 5: every other D1/D10 Coolify mention in cli.py is gone."""

    def test_every_remaining_hit_is_inside_export_or_import_docstrings(self):
        cli_path = REPO_ROOT / "src" / "fabrik" / "cli.py"
        lines = cli_path.read_text().splitlines()
        hit_line_numbers = [i + 1 for i, line in enumerate(lines) if "coolify" in line.lower()]

        export_src, export_start = inspect.getsourcelines(cli_module.export.callback)
        export_end = export_start + len(export_src) - 1
        import_cmd = cli.commands["import"]
        import_src, import_start = inspect.getsourcelines(import_cmd.callback)
        import_end = import_start + len(import_src) - 1

        assert hit_line_numbers, "expected the export docstring's Coolify mention to survive"
        for line_no in hit_line_numbers:
            in_export = export_start <= line_no <= export_end
            in_import = import_start <= line_no <= import_end
            assert in_export or in_import, (
                f"cli.py:{line_no} still mentions Coolify outside export/import: "
                f"{lines[line_no - 1]!r}"
            )


def test_apply_module_still_imports_cleanly():
    # A stale `from fabrik.deploy import ...` anywhere else in the package would
    # fail at import time — re-import the module fresh in a subprocess to prove
    # nothing on the module's import path still reaches the deleted file.
    result = subprocess.run(
        [sys.executable, "-c", "import fabrik.cli"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
