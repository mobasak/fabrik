"""T3-03 — `fabrik review` / `fabrik dev` / `fabrik logs --local` tests.

The three commands share `src/fabrik/dev_tools.py`. We exercise the helpers
directly (deterministic, no docker needed) and the CLI wrappers through
``CliRunner`` to confirm wiring.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from fabrik import dev_tools
from fabrik.cli import cli

# ---------------------------------------------------------------------------
# Helpers — synthetic project tree
# ---------------------------------------------------------------------------


def _make_project(tmp_path: Path, *, with_spec: bool = False, with_preplan: bool = False,
                  with_compose_dev: bool = False) -> Path:
    proj = tmp_path / "test-svc"
    proj.mkdir()
    # always a git repo so `git diff` doesn't fatal
    subprocess.run(["git", "init", "-q"], cwd=str(proj), check=True)
    subprocess.run(["git", "-c", "user.email=t@t.t", "-c", "user.name=t",
                    "commit", "--allow-empty", "-q", "-m", "init"],
                   cwd=str(proj), check=True)
    if with_spec:
        spec_dir = proj / "specs" / "services"
        spec_dir.mkdir(parents=True)
        (spec_dir / "test-svc.yaml").write_text(
            "id: test-svc\n"
            "name: test-svc\n"
            "domain: test-svc.vps1.ocoron.com\n"
            "shape:\n"
            "  needs_database: true\n"
            "  exposes_metrics: true\n"
            "  is_public: true\n",
            encoding="utf-8",
        )
    if with_preplan:
        docs = proj / "docs"
        docs.mkdir()
        (docs / "preplan.md").write_text("# Preplan\n\n## Idea\n\ntest-svc\n", encoding="utf-8")
    if with_compose_dev:
        (proj / "compose.dev.yaml").write_text(
            "services:\n  api:\n    image: alpine\n", encoding="utf-8"
        )
    return proj


# ---------------------------------------------------------------------------
# G-D3 — fabrik review
# ---------------------------------------------------------------------------


class TestReviewBundle:
    def test_find_spec_returns_first_yaml(self, tmp_path):
        proj = _make_project(tmp_path, with_spec=True)
        found = dev_tools.find_spec(proj)
        assert found is not None
        assert found.name == "test-svc.yaml"

    def test_find_spec_none_when_missing(self, tmp_path, monkeypatch):
        proj = _make_project(tmp_path)
        # Point FABRIK_ROOT at an empty tree so the central-spec fallback
        # doesn't find anything either.
        monkeypatch.setattr(dev_tools, "FABRIK_ROOT", tmp_path / "no-fabrik")
        assert dev_tools.find_spec(proj) is None

    def test_find_spec_falls_back_to_central_fabrik_specs(self, tmp_path, monkeypatch):
        # Real-env shape: project has no local specs/ dir, but the fabrik repo
        # carries the spec at <FABRIK_ROOT>/specs/services/<project>.yaml.
        proj = _make_project(tmp_path)
        fake_fabrik = tmp_path / "fake-fabrik-root"
        spec_dir = fake_fabrik / "specs" / "services"
        spec_dir.mkdir(parents=True)
        (spec_dir / f"{proj.name}.yaml").write_text("id: x\n", encoding="utf-8")
        monkeypatch.setattr(dev_tools, "FABRIK_ROOT", fake_fabrik)
        found = dev_tools.find_spec(proj)
        assert found is not None
        assert found.name == f"{proj.name}.yaml"
        assert found.parent == spec_dir

    def test_build_bundle_includes_all_sections(self, tmp_path):
        proj = _make_project(tmp_path, with_spec=True, with_preplan=True)
        spec_path = dev_tools.find_spec(proj)
        content, stats = dev_tools.build_review_bundle(
            proj, since="HEAD", spec_path=spec_path
        )
        assert "# Review bundle" in content
        assert "## Diff" in content
        assert "## Spec" in content
        assert "## Preplan" in content
        assert "## Resolved registrars" in content
        assert stats.spec_lines > 0
        assert stats.preplan_lines > 0

    def test_build_bundle_without_preplan_omits_section(self, tmp_path):
        proj = _make_project(tmp_path, with_spec=True)
        spec_path = dev_tools.find_spec(proj)
        content, stats = dev_tools.build_review_bundle(
            proj, since="HEAD", spec_path=spec_path
        )
        assert "## Preplan" not in content
        assert stats.preplan_lines == 0

    def test_build_bundle_without_spec_omits_spec_and_resolved(self, tmp_path):
        proj = _make_project(tmp_path)
        content, stats = dev_tools.build_review_bundle(
            proj, since="HEAD", spec_path=None
        )
        assert "## Spec" not in content
        assert "## Resolved registrars" not in content
        assert stats.spec_lines == 0
        assert stats.registrars_run == 0

    def test_save_bundle_writes_to_fabrik_review_dir(self, tmp_path):
        proj = _make_project(tmp_path)
        target = dev_tools.save_review_bundle(proj, "# content")
        assert target.exists()
        assert target.parent == proj / ".fabrik" / "review"
        assert target.read_text() == "# content"

    def test_save_bundle_honours_out_override(self, tmp_path):
        proj = _make_project(tmp_path)
        out = proj / "custom.md"
        target = dev_tools.save_review_bundle(proj, "# c", out=out)
        assert target == out
        assert out.read_text() == "# c"

    def test_review_cli_emits_summary(self, tmp_path, monkeypatch):
        proj = _make_project(tmp_path, with_spec=True)
        monkeypatch.chdir(proj)
        runner = CliRunner()
        result = runner.invoke(cli, ["review", "--since", "HEAD"])
        assert result.exit_code == 0, result.output
        assert "📦 Bundling review pack" in result.output
        assert "✅ Bundle saved to" in result.output
        # bundle actually written
        bundles = list((proj / ".fabrik" / "review").glob("*.md"))
        assert len(bundles) == 1


# ---------------------------------------------------------------------------
# G-I1 — fabrik dev
# ---------------------------------------------------------------------------


class TestDevCompose:
    def test_run_dev_returns_minus_one_when_compose_missing(self, tmp_path):
        proj = _make_project(tmp_path)
        rc = dev_tools.run_dev_compose(proj, detach=False, runner=MagicMock())
        assert rc == -1

    def test_run_dev_invokes_docker_compose(self, tmp_path):
        proj = _make_project(tmp_path, with_compose_dev=True)
        fake_runner = MagicMock()
        fake_runner.return_value.returncode = 0
        rc = dev_tools.run_dev_compose(proj, detach=True, runner=fake_runner)
        assert rc == 0
        args = fake_runner.call_args[0][0]
        assert args[:2] == ["docker", "compose"]
        assert "compose.dev.yaml" in args[3]
        assert args[-2:] == ["up", "-d"]

    def test_dev_cli_fails_when_no_compose_dev(self, tmp_path, monkeypatch):
        proj = _make_project(tmp_path)
        monkeypatch.chdir(proj)
        runner = CliRunner()
        result = runner.invoke(cli, ["dev"])
        assert result.exit_code == 1
        assert "No compose.dev.yaml" in result.output


# ---------------------------------------------------------------------------
# G-I2 — fabrik logs --local
# ---------------------------------------------------------------------------


class TestLocalLogs:
    def test_run_local_logs_returns_minus_one_when_compose_missing(self, tmp_path):
        proj = _make_project(tmp_path)
        rc = dev_tools.run_local_logs(proj, service=None, follow=False, runner=MagicMock())
        assert rc == -1

    def test_run_local_logs_invokes_docker_compose(self, tmp_path):
        proj = _make_project(tmp_path, with_compose_dev=True)
        fake_runner = MagicMock()
        fake_runner.return_value.returncode = 0
        rc = dev_tools.run_local_logs(proj, service="api", follow=True, runner=fake_runner)
        assert rc == 0
        args = fake_runner.call_args[0][0]
        assert args[:2] == ["docker", "compose"]
        assert "logs" in args
        assert "-f" in args
        assert "api" in args

    def test_run_local_logs_no_service_no_follow(self, tmp_path):
        proj = _make_project(tmp_path, with_compose_dev=True)
        fake_runner = MagicMock()
        fake_runner.return_value.returncode = 0
        rc = dev_tools.run_local_logs(proj, service=None, follow=False, runner=fake_runner)
        assert rc == 0
        args = fake_runner.call_args[0][0]
        # docker uses "-f <compose-file>" for the compose path; the follow flag
        # would be a *bare* -f appended after "logs". Check no bare -f follow.
        logs_idx = args.index("logs")
        after_logs = args[logs_idx + 1 :]
        assert "-f" not in after_logs
        # last positional is "logs" — no service appended either
        assert after_logs == []

    def test_logs_local_cli_fails_when_no_compose_dev(self, tmp_path, monkeypatch):
        proj = _make_project(tmp_path)
        monkeypatch.chdir(proj)
        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "--local"])
        assert result.exit_code == 1
        assert "No compose.dev.yaml" in result.output

    def test_logs_remote_requires_service(self, tmp_path, monkeypatch):
        proj = _make_project(tmp_path)
        monkeypatch.chdir(proj)
        runner = CliRunner()
        result = runner.invoke(cli, ["logs"])
        assert result.exit_code == 2
        assert "SERVICE argument required" in result.output


# ---------------------------------------------------------------------------
# Smoke: --help on all three commands
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cmd", [
    ["review", "--help"],
    ["dev", "--help"],
    ["logs", "--help"],
])
def test_help_exits_zero(cmd):
    runner = CliRunner()
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0, result.output
