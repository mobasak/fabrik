"""Tests for fabrik.preplan + scaffold preplan ingestion (T3-01)."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from pathlib import Path

import pytest


@pytest.fixture
def fake_root(tmp_path, monkeypatch):
    """Point FABRIK_ROOT at a tmp dir + provision the template + dirs."""
    fake = tmp_path / "fabrik"
    fake.mkdir()
    (fake / "docs" / "preplans").mkdir(parents=True)
    template_dir = fake / "templates" / "preplan"
    template_dir.mkdir(parents=True)

    # Use the real template from the live repo so we're testing the actual
    # rendering — copy it into the fake root.
    real_template = Path("/opt/fabrik/templates/preplan/preplan.md.j2")
    (template_dir / "preplan.md.j2").write_text(real_template.read_text())

    monkeypatch.setenv("FABRIK_ROOT", str(fake))
    import fabrik.config

    importlib.reload(fabrik.config)
    import fabrik.preplan

    importlib.reload(fabrik.preplan)
    return fake


# ─────────────────────────────────────────────────────────────────────────────
# create_preplan
# ─────────────────────────────────────────────────────────────────────────────


class TestCreatePreplan:
    def test_creates_dated_file(self, fake_root):
        from fabrik.preplan import create_preplan

        path = create_preplan("my-test")
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        assert path.name == f"{today}-my-test.md"
        assert path.exists()

    def test_renders_slug_and_date_substitution(self, fake_root):
        from fabrik.preplan import create_preplan

        path = create_preplan("citation-verifier", date="2026-05-15")
        content = path.read_text()
        assert "# Preplan — citation-verifier" in content
        assert "**Date:** 2026-05-15" in content
        assert "citation_verifier" in content  # slug | replace('-', '_') in DB hint
        assert "citation-verifier.vps1.ocoron.com" in content

    def test_refuses_to_overwrite(self, fake_root):
        from fabrik.preplan import create_preplan

        create_preplan("dup-slug")
        with pytest.raises(FileExistsError):
            create_preplan("dup-slug")

    def test_invalid_slug_rejected(self, fake_root):
        from fabrik.preplan import create_preplan

        # Leading dash, special chars, too long, etc.
        for bad in ["-leading", "trailing-", "UPPER", "has space", "with/slash"]:
            with pytest.raises(ValueError):
                create_preplan(bad)

    def test_invalid_date_rejected(self, fake_root):
        from fabrik.preplan import create_preplan

        with pytest.raises(ValueError):
            create_preplan("ok", date="not-a-date")
        with pytest.raises(ValueError):
            create_preplan("ok", date="2026-13-99")  # bad month


# ─────────────────────────────────────────────────────────────────────────────
# parse_preplan
# ─────────────────────────────────────────────────────────────────────────────


class TestParsePreplan:
    def test_parses_freshly_rendered_template(self, fake_root):
        from fabrik.preplan import create_preplan, parse_preplan

        path = create_preplan("freshparse", date="2026-05-15")
        pp = parse_preplan(path)
        assert pp.slug == "freshparse"
        assert pp.date == "2026-05-15"
        assert pp.project_type == "python-api"  # template default
        # Shape block should round-trip
        assert pp.shape.get("kind") == "service"
        assert pp.shape.get("is_public") is True
        assert pp.shape.get("exposes_metrics") is True
        # Domain
        assert pp.domain == "freshparse.vps1.ocoron.com"

    def test_missing_file_raises(self, fake_root):
        from fabrik.preplan import parse_preplan

        with pytest.raises(FileNotFoundError):
            parse_preplan(fake_root / "docs" / "preplans" / "no-such.md")

    def test_invalid_project_type_raises(self, fake_root):
        from fabrik.preplan import parse_preplan

        bad = fake_root / "docs" / "preplans" / "2026-05-15-bad.md"
        bad.write_text(
            "# Preplan — bad\n\n## 1. Idea\n\nfoo\n\n## 2. Project type\n\n"
            "**Selected:** `made-up-type`\n"
        )
        with pytest.raises(ValueError, match="not a valid scaffold type"):
            parse_preplan(bad)

    def test_external_deps_table_parsed(self, fake_root):
        from fabrik.preplan import parse_preplan

        p = fake_root / "docs" / "preplans" / "2026-05-15-deps.md"
        p.write_text(
            "# Preplan — deps\n\n## 2. Project type\n\n**Selected:** `python-api`\n\n"
            "## 4. External deps\n\n"
            "| Dep | Why | Secret name (env var) | Cost / quota |\n"
            "|---|---|---|---|\n"
            "| NCBI | citations | `NCBI_API_KEY` | free |\n"
            "| Crossref | metadata | `CROSSREF_MAILTO` | free |\n"
        )
        pp = parse_preplan(p)
        assert len(pp.external_deps) == 2
        assert pp.external_deps[0]["dep"] == "NCBI"
        assert "NCBI_API_KEY" in pp.external_deps[0]["secret_env_var"]

    def test_bullet_lists_skip_template_placeholders(self, fake_root):
        from fabrik.preplan import parse_preplan

        p = fake_root / "docs" / "preplans" / "2026-05-15-bullets.md"
        p.write_text(
            "# Preplan — bullets\n\n## 2. Project type\n\n**Selected:** `python-api`\n\n"
            "## 6. Success criteria\n\n"
            "- [ ] _e.g._ this is a placeholder example\n"
            "- [ ] real criterion: returns 200 on /health\n"
        )
        pp = parse_preplan(p)
        assert len(pp.success_criteria) == 1  # placeholder filtered
        assert "returns 200" in pp.success_criteria[0]


# ─────────────────────────────────────────────────────────────────────────────
# Scaffold ingestion: _layer_preplan_into_project
# ─────────────────────────────────────────────────────────────────────────────


class TestLayerPreplanIntoProject:
    def test_copies_preplan_to_project_docs(self, fake_root, tmp_path):
        from fabrik.preplan import create_preplan, parse_preplan
        from fabrik.scaffold import _layer_preplan_into_project

        preplan_path = create_preplan("layered", date="2026-05-15")
        pp = parse_preplan(preplan_path)

        project_dir = tmp_path / "fake-project"
        project_dir.mkdir()

        _layer_preplan_into_project(project_dir, pp)
        copied = project_dir / "docs" / "preplan.md"
        assert copied.exists()
        assert copied.read_text() == preplan_path.read_text()

    def test_injects_reference_into_all_4_guardrails(self, fake_root, tmp_path):
        from fabrik.preplan import create_preplan, parse_preplan
        from fabrik.scaffold import _layer_preplan_into_project

        preplan_path = create_preplan("guardrails", date="2026-05-15")
        pp = parse_preplan(preplan_path)

        project_dir = tmp_path / "fake-project"
        project_dir.mkdir()
        # Create all 4 guardrail files with minimal stub content
        for fname in ("AGENTS.md", "CLAUDE.md", "AGENTS-compact.md", ".windsurfrules"):
            (project_dir / fname).write_text(f"# {fname}\n\nExisting content.\n")

        _layer_preplan_into_project(project_dir, pp)

        for fname in ("AGENTS.md", "CLAUDE.md", "AGENTS-compact.md", ".windsurfrules"):
            content = (project_dir / fname).read_text()
            assert "Preplan:" in content
            assert "docs/preplan.md" in content
            # Original content preserved
            assert "Existing content." in content

    def test_skips_missing_guardrail_files_silently(self, fake_root, tmp_path):
        from fabrik.preplan import create_preplan, parse_preplan
        from fabrik.scaffold import _layer_preplan_into_project

        preplan_path = create_preplan("partial", date="2026-05-15")
        pp = parse_preplan(preplan_path)

        project_dir = tmp_path / "fake-project"
        project_dir.mkdir()
        # Only one of the 4 guardrails exists
        (project_dir / "AGENTS.md").write_text("# AGENTS\n")
        # Don't create CLAUDE.md / AGENTS-compact.md / .windsurfrules

        # Should not raise
        _layer_preplan_into_project(project_dir, pp)

        assert "Preplan:" in (project_dir / "AGENTS.md").read_text()
        assert not (project_dir / "CLAUDE.md").exists()

    def test_idempotent_does_not_duplicate_reference(self, fake_root, tmp_path):
        from fabrik.preplan import create_preplan, parse_preplan
        from fabrik.scaffold import _layer_preplan_into_project

        preplan_path = create_preplan("idempotent", date="2026-05-15")
        pp = parse_preplan(preplan_path)

        project_dir = tmp_path / "fake-project"
        project_dir.mkdir()
        (project_dir / "AGENTS.md").write_text("# AGENTS\n")

        _layer_preplan_into_project(project_dir, pp)
        first_content = (project_dir / "AGENTS.md").read_text()

        # Second invocation should be a no-op for files that already
        # contain "Preplan:" + "docs/preplan.md"
        _layer_preplan_into_project(project_dir, pp)
        second_content = (project_dir / "AGENTS.md").read_text()

        assert first_content == second_content
        # Only one Preplan: reference, not two
        assert first_content.count("Preplan:") == 1

    def test_none_preplan_is_no_op(self, tmp_path):
        from fabrik.scaffold import _layer_preplan_into_project

        project_dir = tmp_path / "empty-project"
        project_dir.mkdir()
        _layer_preplan_into_project(project_dir, None)
        # No files created
        assert list(project_dir.iterdir()) == []


# ─────────────────────────────────────────────────────────────────────────────
# CLI surface check
# ─────────────────────────────────────────────────────────────────────────────


class TestCLISurface:
    def test_preplan_is_a_group_not_hyphenated_command(self):
        """fabrik preplan new <slug>` works (space), `fabrik preplan-new` does NOT.

        This is the canonical @cli.group + @preplan.command("new") pattern
        check from the ticket's BLOCKER FIX.
        """
        from click.testing import CliRunner

        from fabrik.cli import cli

        runner = CliRunner()

        # `fabrik preplan --help` should list `new` as a subcommand
        result = runner.invoke(cli, ["preplan", "--help"])
        assert result.exit_code == 0
        assert "new" in result.output

        # `fabrik preplan-new` should NOT be a registered command
        result_bad = runner.invoke(cli, ["preplan-new", "--help"])
        assert result_bad.exit_code != 0
