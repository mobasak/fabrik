"""Tests for fix_project() AFCL preservation + reference-doc refresh behavior."""

import os
from pathlib import Path

import pytest

from fabrik.scaffold import fix_project

FABRIK_ROOT = Path("/opt/fabrik")
# the guard's own message: a bare "hub" also matches any unrelated error that echoes a path containing it
_REFUSAL = "refusing to scaffold/fix the Fabrik hub"


def _source_root() -> Path:
    """The root fix_project copies the reference docs from — `config._resolve_fabrik_root()`'s answer."""
    import fabrik.scaffold as scaffold

    return scaffold.FABRIK_ROOT


requires_fabrik_env = pytest.mark.skipif(
    not FABRIK_ROOT.exists() or os.getenv("CI") == "true",
    reason="Requires full fabrik environment at /opt/fabrik (not available in CI)",
)


class TestScaffoldHubGuard:
    """scaffold/fix must refuse to target the Fabrik hub (/opt/fabrik) itself.

    Regression guard: writing the project synced-gitignore block to the hub
    would ignore the hub's own canonical sources (.windsurf/, CLAUDE.md, …).
    """

    @pytest.fixture()
    def fake_hub(self, tmp_path, monkeypatch):
        """A hub checkout in tmp_path, recognised only by its marker (FABRIK_ROOT points elsewhere).

        These guard tests never aim fix_project at the real /opt/fabrik: if the guard regressed,
        that call would rewrite the shared checkout (2026-09-24, W-508064a8), and on a machine
        without /opt/fabrik (CI) it would run against a missing path (W-a6d1dbf5)."""
        import fabrik.scaffold as scaffold

        monkeypatch.setattr(scaffold, "FABRIK_ROOT", tmp_path / "elsewhere")
        hub = tmp_path / "hub"
        (hub / "src" / "fabrik").mkdir(parents=True)
        (hub / "src" / "fabrik" / "scaffold.py").write_text("")
        return hub

    def test_fix_project_refuses_hub(self, fake_hub):
        with pytest.raises(ValueError, match=_REFUSAL):
            fix_project(fake_hub)

    def test_assert_not_hub_refuses_hub_and_dotpath(self, fake_hub):
        from fabrik.scaffold import _assert_not_hub

        with pytest.raises(ValueError, match=_REFUSAL):
            _assert_not_hub(fake_hub)
        # Path normalization: <parent>/missing/../hub reaches the hub only once resolve() collapses
        # the ".." — no lexical parent of the unresolved path carries the marker.
        with pytest.raises(ValueError, match=_REFUSAL):
            _assert_not_hub(fake_hub.parent / "missing" / ".." / fake_hub.name)

    def test_assert_not_hub_allows_non_hub(self):
        from fabrik.scaffold import _assert_not_hub

        # A normal project path must not trip the guard.
        _assert_not_hub(Path("/opt/some-other-project"))

    def test_assert_not_hub_blocks_hub_subdir(self, fake_hub):
        """Residual-risk R4 closed: a path INSIDE the hub is also refused."""
        from fabrik.scaffold import _assert_not_hub

        with pytest.raises(ValueError, match=_REFUSAL):
            _assert_not_hub(fake_hub / "docs" / "x")

    def test_assert_not_hub_blocks_symlink_to_hub(self, fake_hub, tmp_path):
        """A link to a hub checkout is refused (its marker is visible through the link)."""
        from fabrik.scaffold import _assert_not_hub

        link = tmp_path / "hublink"
        link.symlink_to(fake_hub)
        with pytest.raises(ValueError, match=_REFUSAL):
            _assert_not_hub(link)

    def test_the_configured_root_is_refused_without_a_marker(self, tmp_path, monkeypatch):
        """The FABRIK_ROOT branch alone: a root carrying no marker, and a link into it, are refused."""
        import fabrik.scaffold as scaffold

        root = tmp_path / "configured-root"
        root.mkdir()
        monkeypatch.setattr(scaffold, "FABRIK_ROOT", root)
        link = tmp_path / "rootlink"
        link.symlink_to(root)
        # Only resolve() puts <link>/new-project under the root; no marker exists to catch it.
        for target in (root, root / "new-project", link / "new-project"):
            with pytest.raises(ValueError, match=_REFUSAL):
                scaffold._assert_not_hub(target)
        # A sibling sharing the root's name prefix is not inside it (a string-prefix guard fails here).
        scaffold._assert_not_hub(tmp_path / "configured-root-2")
        # The root itself configured through a link: the guard must resolve FABRIK_ROOT too.
        monkeypatch.setattr(scaffold, "FABRIK_ROOT", link)
        with pytest.raises(ValueError, match=_REFUSAL):
            scaffold._assert_not_hub(root / "new-project")

    def test_create_project_refuses_a_hub_base(self, fake_hub):
        """The scaffold path calls the guard too, before anything is written."""
        from fabrik.scaffold import create_project

        with pytest.raises(ValueError, match=_REFUSAL):
            create_project("new-project", "d", base=fake_hub, generate_spec=False)
        assert not (fake_hub / "new-project").exists()

    @requires_fabrik_env
    def test_hub_is_refused_when_fabrik_root_points_elsewhere(self, tmp_path, monkeypatch):
        """W-508064a8: with FABRIK_ROOT pointed at a worktree, the real hub was 'not the hub'.

        That override is what the scaffold tests need (templates resolve through it), and on
        2026-09-24 it let test_fix_project_refuses_hub rewrite the shared checkout.
        """
        import fabrik.scaffold as scaffold

        monkeypatch.setattr(scaffold, "FABRIK_ROOT", tmp_path / "some-worktree")
        with pytest.raises(ValueError, match=_REFUSAL):
            scaffold._assert_not_hub(FABRIK_ROOT)
        with pytest.raises(ValueError, match=_REFUSAL):
            scaffold._assert_not_hub(FABRIK_ROOT / "templates" / "x")

    def test_any_hub_checkout_is_refused_by_its_markers(self, tmp_path, monkeypatch):
        """A hub checkout (a worktree or clone) is recognised by its own files, not its path."""
        import fabrik.scaffold as scaffold

        monkeypatch.setattr(scaffold, "FABRIK_ROOT", tmp_path / "elsewhere")
        # An old-revision clone (no synced manifest yet) is still a hub: the scaffolder is the marker.
        hub = tmp_path / "hub-clone"
        (hub / "src" / "fabrik").mkdir(parents=True)
        (hub / "src" / "fabrik" / "scaffold.py").write_text("")
        # A partial checkout where the marker path is a directory, or a dangling link, still counts.
        odd_dir = tmp_path / "partial-checkout"
        (odd_dir / "src" / "fabrik" / "scaffold.py").mkdir(parents=True)
        dangling = tmp_path / "dangling-checkout"
        (dangling / "src" / "fabrik").mkdir(parents=True)
        (dangling / "src" / "fabrik" / "scaffold.py").symlink_to(tmp_path / "gone")
        for target in (hub, hub / "docs" / "deep", odd_dir, dangling / "new-project"):
            with pytest.raises(ValueError, match=_REFUSAL):
                scaffold._assert_not_hub(target)

    def test_synced_project_files_do_not_make_a_hub(self, tmp_path, monkeypatch):
        """Over-block guard: a project carrying the hub's synced files is still scaffoldable."""
        import fabrik.scaffold as scaffold

        monkeypatch.setattr(scaffold, "FABRIK_ROOT", tmp_path / "elsewhere")
        project = tmp_path / "project"
        (project / "scripts" / "enforcement").mkdir(parents=True)
        (project / "scripts" / "fabrik_synced_manifest.py").write_text("")
        (project / "src" / "project").mkdir(parents=True)
        (project / "src" / "project" / "scaffold.py").write_text("")
        scaffold._assert_not_hub(project)
        scaffold._assert_not_hub(project / "not-yet-created")


@requires_fabrik_env
class TestFixProjectAFCLPreservation:
    """fix_project() must NOT overwrite project-local AFCL.md content."""

    def test_existing_afcl_with_custom_content_is_preserved(self, tmp_path):
        """AFCL.md with project-specific findings survives fabrik fix."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        custom_afcl = "# AFCL\n\n## Friction 1\n\nProject-local lore must survive.\n"
        afcl_path = project_dir / "AFCL.md"
        afcl_path.write_text(custom_afcl)

        added = fix_project(project_dir, project_type="python-api", dry_run=False)

        assert afcl_path.read_text() == custom_afcl, "AFCL.md was overwritten"
        assert not any("AFCL.md" in entry for entry in added), (
            "fix_project reported AFCL change despite preserving it"
        )

    def test_missing_afcl_is_created_from_template(self, tmp_path):
        """AFCL.md is created from template when missing."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        afcl_path = project_dir / "AFCL.md"
        assert not afcl_path.exists()

        added = fix_project(project_dir, project_type="python-api", dry_run=False)

        if (FABRIK_ROOT / "templates" / "scaffold" / "AFCL_TEMPLATE.md").exists():
            assert afcl_path.exists(), "AFCL.md was not created from template"
            assert "AFCL.md (created)" in added

    def test_dry_run_reports_afcl_only_when_missing(self, tmp_path):
        """Dry-run preview matches the live behavior: AFCL only-if-missing."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        # Case 1: AFCL exists -> dry_run must NOT report it
        (project_dir / "AFCL.md").write_text("# Custom AFCL\n")
        added_with = fix_project(project_dir, project_type="python-api", dry_run=True)
        assert not any("AFCL.md" in entry for entry in added_with), (
            "dry_run reported AFCL.md change when file already exists"
        )

        # Case 2: AFCL missing -> dry_run must report (created)
        (project_dir / "AFCL.md").unlink()
        added_without = fix_project(project_dir, project_type="python-api", dry_run=True)
        if (FABRIK_ROOT / "templates" / "scaffold" / "AFCL_TEMPLATE.md").exists():
            assert "AFCL.md (created)" in added_without


@requires_fabrik_env
class TestFixProjectReferenceDocsRefresh:
    """fix_project() MUST overwrite reference docs from canonical Fabrik root."""

    def test_stack_decision_guide_is_overwritten_when_target_exists(self, tmp_path):
        """technology-stack-decision-guide.md is refreshed even if target exists."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        ref_dir = project_dir / "docs" / "reference"
        ref_dir.mkdir(parents=True)
        target = ref_dir / "technology-stack-decision-guide.md"
        stale_marker = "# STALE LOCAL COPY — must be replaced\n"
        target.write_text(stale_marker)

        added = fix_project(project_dir, project_type="python-api", dry_run=False)

        canonical = (
            _source_root() / "docs" / "reference" / "technology-stack-decision-guide.md"
        ).read_text()
        assert target.read_text() == canonical, "Reference doc was not refreshed from master"
        assert target.read_text() != stale_marker
        assert any("technology-stack-decision-guide.md (refreshed from master)" in e for e in added)

    def test_prebuilt_containers_is_overwritten_when_target_exists(self, tmp_path):
        """prebuilt-app-containers.md is refreshed even if target exists."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        ref_dir = project_dir / "docs" / "reference"
        ref_dir.mkdir(parents=True)
        target = ref_dir / "prebuilt-app-containers.md"
        target.write_text("# stale\n")

        added = fix_project(project_dir, project_type="python-api", dry_run=False)

        canonical = (
            _source_root() / "docs" / "reference" / "prebuilt-app-containers.md"
        ).read_text()
        assert target.read_text() == canonical
        assert any("prebuilt-app-containers.md (refreshed from master)" in e for e in added)

    def test_kilo_47_agents_json_is_removed_never_copied(self, tmp_path):
        """A project's kilo_47_agents_final.json is retired (D-529): removed, never re-copied."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        scripts_dir = project_dir / "scripts"
        scripts_dir.mkdir()
        target = scripts_dir / "kilo_47_agents_final.json"
        target.write_text('{"stale": true}\n')

        added = fix_project(project_dir, project_type="python-api", dry_run=False)

        assert not target.exists()
        assert "removed scripts/kilo_47_agents_final.json" in added
        assert not any("refreshed from master" in e and "kilo_47" in e for e in added)

    def test_dry_run_previews_reference_doc_refresh(self, tmp_path):
        """dry_run reports the reference-doc refresh and the kilo_47 removal, touching nothing."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()
        (project_dir / "scripts").mkdir()
        kilo = project_dir / "scripts" / "kilo_47_agents_final.json"
        kilo.write_text("{}\n")

        added = fix_project(project_dir, project_type="python-api", dry_run=True)

        if (_source_root() / "docs" / "reference" / "technology-stack-decision-guide.md").exists():
            assert any(
                "technology-stack-decision-guide.md (refreshed from master)" in e for e in added
            )
        if (_source_root() / "docs" / "reference" / "prebuilt-app-containers.md").exists():
            assert any("prebuilt-app-containers.md (refreshed from master)" in e for e in added)
        assert "removed scripts/kilo_47_agents_final.json" in added
        assert kilo.read_text() == "{}\n"


@requires_fabrik_env
class TestFixProjectReadsTheDeclaredType:
    """W-526528b6: `fabrik fix` repaired every project from the python-api map unless --type was passed."""

    def _saas_project(self, tmp_path: Path) -> Path:
        project_dir = tmp_path / "saas-project"
        (project_dir / ".git").mkdir(parents=True)
        (project_dir / "project.yaml").write_text("name: saas-project\ntype: saas-skeleton\n")
        return project_dir

    def test_declared_type_drives_the_repair(self, tmp_path):
        project_dir = self._saas_project(tmp_path)

        added = fix_project(project_dir, dry_run=False)

        assert "[unsupported-fix] server/Dockerfile" in added
        assert not (project_dir / "server").exists(), "a placeholder or stray dir was written"
        assert not (project_dir / "src").exists(), (
            "python-api files were seeded into a saas project"
        )

    def test_dry_run_reports_what_the_live_run_would(self, tmp_path):
        project_dir = self._saas_project(tmp_path)

        preview = fix_project(project_dir, dry_run=True)

        assert "[unsupported-fix] server/Dockerfile" in preview
        assert "server/Dockerfile" not in preview

    def test_explicit_type_overrides_the_declared_one(self, tmp_path):
        project_dir = self._saas_project(tmp_path)

        added = fix_project(project_dir, dry_run=True, project_type="python-api")

        assert not any("server/" in entry for entry in added)

    def test_no_declared_type_and_none_passed_is_refused(self, tmp_path):
        project_dir = tmp_path / "bare"
        (project_dir / ".git").mkdir(parents=True)

        with pytest.raises(ValueError, match="--type"):
            fix_project(project_dir, dry_run=True)
        assert list(project_dir.iterdir()) == [project_dir / ".git"]

    def test_cli_prints_the_refusal_and_exits_nonzero(self, tmp_path):
        from click.testing import CliRunner

        from fabrik.cli import cli

        project_dir = tmp_path / "bare"
        (project_dir / ".git").mkdir(parents=True)

        result = CliRunner().invoke(cli, ["fix", str(project_dir), "--dry-run"])

        assert result.exit_code == 1
        assert "--type" in result.stderr
        assert "--type" not in result.stdout

    def test_cli_lists_unrepairable_files_apart_from_added_ones(self, tmp_path):
        from click.testing import CliRunner

        from fabrik.cli import cli

        project_dir = self._saas_project(tmp_path)

        result = CliRunner().invoke(cli, ["fix", str(project_dir), "--dry-run"])

        assert result.exit_code == 1, "a project left incomplete must not exit 0"
        assert "not repairable by fix (re-run the scaffolder): server/Dockerfile" in result.stdout
        assert "📄 [unsupported-fix]" not in result.output
        assert "stay missing" in result.stderr

    def test_python_api_gpu_is_repaired_from_the_python_api_templates(self, tmp_path):
        """python-api-gpu shares the python-api layout, so its Dockerfile has a real template."""
        project_dir = tmp_path / "gpu-project"
        (project_dir / ".git").mkdir(parents=True)
        (project_dir / "project.yaml").write_text("name: gpu-project\ntype: python-api-gpu\n")

        added = fix_project(project_dir, dry_run=False)

        assert "Dockerfile" in added
        assert not any(entry.startswith("[unsupported-fix]") for entry in added)
        assert "FROM" in (project_dir / "Dockerfile").read_text()

    def test_a_non_string_type_is_refused_not_crashed(self, tmp_path):
        project_dir = tmp_path / "odd"
        (project_dir / ".git").mkdir(parents=True)
        (project_dir / "project.yaml").write_text("name: odd\ntype: [python-api]\n")

        with pytest.raises(ValueError, match="--type"):
            fix_project(project_dir, dry_run=True)

    def test_a_non_mapping_project_yaml_with_explicit_type_does_not_crash(self, tmp_path):
        project_dir = tmp_path / "listy"
        (project_dir / ".git").mkdir(parents=True)
        (project_dir / "project.yaml").write_text("- a\n- b\n")

        fix_project(project_dir, dry_run=True, project_type="python-api")

    def test_cli_validate_checks_the_declared_type(self, tmp_path):
        from click.testing import CliRunner

        from fabrik.cli import cli

        project_dir = self._saas_project(tmp_path)

        result = CliRunner().invoke(cli, ["validate", str(project_dir)])

        assert result.exit_code == 1
        assert "server/Dockerfile" in result.stdout
        assert f"Run: fabrik fix {project_dir}\n" in result.stdout, "the hint must not pin a type"

    def test_cli_validate_without_a_type_is_refused(self, tmp_path):
        from click.testing import CliRunner

        from fabrik.cli import cli

        project_dir = tmp_path / "bare"
        (project_dir / ".git").mkdir(parents=True)

        result = CliRunner().invoke(cli, ["validate", str(project_dir)])

        assert result.exit_code == 1
        assert "--type" in result.stderr

    def test_a_type_without_its_own_list_is_held_to_the_shared_files(self, tmp_path):
        """wordpress has no TYPE_REQUIRED_FILES entry; it must not inherit python-api's Dockerfile."""
        from fabrik.scaffold import validate_project

        project_dir = tmp_path / "wp"
        (project_dir / ".git").mkdir(parents=True)
        (project_dir / "project.yaml").write_text("name: wp\ntype: wordpress\n")

        _, missing = validate_project(project_dir, "wordpress")

        assert "Dockerfile" not in missing
        assert not any(
            e.startswith("[unsupported-fix]") for e in fix_project(project_dir, dry_run=True)
        )

    def test_refusal_hint_names_the_project_path(self, tmp_path):
        project_dir = tmp_path / "typeless"
        (project_dir / ".git").mkdir(parents=True)
        (project_dir / "project.yaml").write_text("name: typeless\n")

        with pytest.raises(ValueError, match=f"fabrik fix {project_dir} --type"):
            fix_project(project_dir, dry_run=True)

    def test_cli_prints_no_added_summary_when_nothing_was_added(self, tmp_path):
        from unittest import mock

        from click.testing import CliRunner

        from fabrik.cli import cli

        project_dir = self._saas_project(tmp_path)
        only_unsupported = ["[unsupported-fix] server/Dockerfile"]
        with mock.patch("fabrik.scaffold.fix_project", return_value=only_unsupported):
            result = CliRunner().invoke(cli, ["fix", str(project_dir)])

        assert result.exit_code == 1
        assert "Added 0 files" not in result.output


_TEMPLATE_HEADER = "# Fabrik template rules (mobile-app) - added by fabrik fix"


def _mobile_project(root: Path, gitignore: str | None) -> Path:
    root.mkdir()
    (root / ".git").mkdir()
    if gitignore is not None:
        (root / ".gitignore").write_text(gitignore)
    return root


@requires_fabrik_env
class TestFixBackfillsTemplateGitignoreRules:
    """W-6fa329b3: fabrik fix backfills templates/<type>/.gitignore into existing projects."""

    def test_fix_backfills_missing_template_gitignore_rules(self, tmp_path):
        original = ".env\n*.log\n/build/\n"
        proj = _mobile_project(tmp_path / "mob", original)
        added = fix_project(proj, project_type="mobile-app")
        text = (proj / ".gitignore").read_text()
        lines = text.splitlines()
        assert lines[0] == _TEMPLATE_HEADER
        head = lines[: lines.index("") if "" in lines else len(lines)]
        for rule in ("node_modules/", ".env*.local", "*.jks", "*.p8", "*.p12", "*.mobileprovision"):
            assert rule in head, rule
        assert "*.log" not in head, "a rule the project already has is not re-added"
        after_block = text.split("\n\n", 1)[1]
        assert after_block.startswith(original), (
            "every original line stays, unchanged, after the block"
        )
        assert any(
            e.startswith(".gitignore (") and "template rules:" in e and "*.p8" in e for e in added
        ), added

        py = _mobile_project(tmp_path / "py", original)
        fix_project(py, project_type="python-api")
        assert _TEMPLATE_HEADER.split(" (")[0] not in (py / ".gitignore").read_text()

    def test_fix_template_gitignore_backfill_is_idempotent_and_reuses_its_block(self, tmp_path):
        proj = _mobile_project(tmp_path / "mob", ".env\n")
        fix_project(proj, project_type="mobile-app")
        first = (proj / ".gitignore").read_text()
        assert _TEMPLATE_HEADER in first
        added = fix_project(proj, project_type="mobile-app")
        assert (proj / ".gitignore").read_text() == first
        assert not any(e.startswith(".gitignore (+") for e in added), added
        (proj / ".gitignore").write_text(first.replace("*.p8\n", "", 1))
        fix_project(proj, project_type="mobile-app")
        again = (proj / ".gitignore").read_text()
        assert again.count(_TEMPLATE_HEADER) == 1
        assert "*.p8" in again.splitlines()

    def test_fix_backfill_treats_a_slashless_rule_as_present(self, tmp_path):
        from fabrik.scaffold import _patch_template_gitignore_rules

        new, rules = _patch_template_gitignore_rules("node_modules\n", "mobile-app")
        assert "node_modules/" not in rules
        assert "*.jks" in rules and "*.jks" in new.splitlines()
        # the slash is dropped on the template side only: a project `*.p8/` does not cover `*.p8`
        _, rules2 = _patch_template_gitignore_rules("*.p8/\n", "mobile-app")
        assert "*.p8" in rules2

    def test_fix_backfill_never_defeats_a_project_reinclude(self, tmp_path):
        from fabrik.scaffold import _patch_template_gitignore_rules

        new, rules = _patch_template_gitignore_rules(
            "android/*\n!android/app/debug.keystore\n", "mobile-app"
        )
        assert "/android/" not in rules, "an excluded dir would kill the project's re-include"
        assert "*.jks" in rules and "/ios/" in rules
        new2, _ = _patch_template_gitignore_rules(".env.*\n!.env.test.local\n", "mobile-app")
        lines = new2.splitlines()
        assert lines.index(".env*.local") < lines.index("!.env.test.local"), (
            "the block sits above the project's negation, so the negation wins"
        )

    def test_fix_backfill_dry_run_matches_live_and_writes_nothing(self, tmp_path):
        original = ".env\n.droid/reviews/\n"
        dry = _mobile_project(tmp_path / "dry", original)
        live = _mobile_project(tmp_path / "live", original)
        dry_added = fix_project(dry, project_type="mobile-app", dry_run=True)
        assert (dry / ".gitignore").read_text() == original
        live_added = fix_project(live, project_type="mobile-app")
        pick = [e for e in dry_added if e.startswith(".gitignore")]
        assert any("template rules:" in e for e in pick), pick
        assert pick == [e for e in live_added if e.startswith(".gitignore")]

    def test_fix_backfill_keeps_the_droid_block_patch(self, tmp_path):
        from fabrik.scaffold import _DROID_GITIGNORE_BLOCK

        proj = _mobile_project(tmp_path / "mob", ".env\n.droid/reviews/\n.droid/kilo_usage.jsonl\n")
        added = fix_project(proj, project_type="mobile-app")
        text = (proj / ".gitignore").read_text()
        assert text.count(_DROID_GITIGNORE_BLOCK) == 1
        assert ".droid/reviews/" not in text.splitlines()
        assert _TEMPLATE_HEADER in text
        entries = [e for e in added if e.startswith(".gitignore")]
        assert len(entries) == 1, "one file, one entry — the CLI counts entries as files"
        assert entries[0].startswith(".gitignore (.droid/ block updated, +"), entries

    def test_fix_backfill_creates_a_missing_gitignore(self, tmp_path, monkeypatch):
        from fabrik.scaffold import _DROID_GITIGNORE_BLOCK

        proj = _mobile_project(tmp_path / "mob", None)
        added = fix_project(proj, project_type="mobile-app")
        text = (proj / ".gitignore").read_text()
        assert text.splitlines()[0] == _TEMPLATE_HEADER and "*.p8" in text.splitlines()
        assert _DROID_GITIGNORE_BLOCK in text, "the created file carries the .droid/ block too"
        assert any(e.startswith(".gitignore (created, +") for e in added), added
        again = fix_project(proj, project_type="mobile-app")
        assert (proj / ".gitignore").read_text() == text, "one run settles the file"
        assert not any(e.startswith(".gitignore") for e in again), again

        import fabrik.scaffold as scaffold

        monkeypatch.setattr(scaffold, "MOBILE_APP_TEMPLATE_DIR", tmp_path / "no-such-template")
        with pytest.raises(FileNotFoundError):
            scaffold._patch_template_gitignore_rules("", "mobile-app")

    def test_fix_backfill_covers_node_api(self, tmp_path):
        proj = _mobile_project(tmp_path / "node", ".env\n")
        added = fix_project(proj, project_type="node-api")
        lines = (proj / ".gitignore").read_text().splitlines()
        assert lines[0] == "# Fabrik template rules (node-api) - added by fabrik fix"
        assert "node_modules/" in lines and "npm-debug.log*" in lines
        assert lines.count(".env") == 1, "the project's own .env is not re-added"
        assert any("template rules" in e for e in added), added

    def test_fix_backfill_reinclude_forms(self, tmp_path):
        from fabrik.scaffold import _patch_template_gitignore_rules as patch

        # a re-include BENEATH a directory the rule excludes: a whole-dir glob, any depth
        for project in ("!ios/**\n", "!/ios/*\n", "!**/ios/Podfile\n"):
            _, rules = patch(project, "mobile-app")
            assert "/ios/" not in rules, project
            assert "/android/" in rules, project
        # an unanchored dir rule can hide a nested re-include, and a literal name can match a glob rule
        _, rules = patch("!packages/app/node_modules/keep.js\n", "mobile-app")
        assert "node_modules/" not in rules
        _, rules = patch("!old.jks/notes.txt\n", "mobile-app")
        assert "*.jks" not in rules
        # an EXACT re-include, however anchored or dir-only, is never a skip: the rule goes above it
        # and the later negation wins, while skipping would leave nested or file matches unprotected
        for project, rule in (
            ("!*.jks\n", "*.jks"),
            ("!/*.jks\n", "*.jks"),
            ("!*.jks/\n", "*.jks"),
            ("!.env*.local/\n", ".env*.local"),
            ("!/node_modules\n", "node_modules/"),
            ("!/ios/\n", "/ios/"),
        ):
            new, rules = patch(project, "mobile-app")
            assert rule in rules, (project, rule)
            lines = new.splitlines()
            assert lines.index(rule) < lines.index(project.strip()), (project, rule)
        # a WILDCARD ancestor segment never counts, or every rule would be skipped, signing ones included
        signing = ("*.jks", "*.p8", "*.p12", "*.key", "*.mobileprovision", ".env*.local")
        wildcard = ("!*/.gitkeep\n", "!src/*/keep\n", "!i*/Podfile\n", "!**/*/x\n")
        for project in (*wildcard, "!*.jks/keep\n", "!?.p8/x\n"):
            _, rules = patch(project, "mobile-app")
            for rule in (*signing, "node_modules/", "/ios/", "/android/"):
                assert rule in rules, (project, rule)
        # a re-include that only overlaps a FILE pattern never drops the signing rule
        new, rules = patch("!keys/test.p8\n", "mobile-app")
        assert "*.p8" in rules
        lines = new.splitlines()
        assert lines.index("*.p8") < lines.index("!keys/test.p8")

    def test_fix_backfill_leading_slash_variant_is_present(self, tmp_path):
        from fabrik.scaffold import _patch_template_gitignore_rules as patch

        _, rules = patch("ios/\nandroid\n", "mobile-app")
        assert "/ios/" not in rules and "/android/" not in rules
        # the reverse never holds: an anchored project line does not cover an unanchored rule
        _, rules = patch("/node_modules/\n", "mobile-app")
        assert "node_modules/" in rules

    def test_fix_backfill_header_placement(self, tmp_path):
        from fabrik.scaffold import _patch_template_gitignore_rules as patch

        full, _ = patch("", "mobile-app")
        block = full.replace("*.p8\n", "", 1)
        new, rules = patch("*.tmp\n" + block + "keep.txt\n", "mobile-app")
        lines = new.splitlines()
        assert rules == ["*.p8"]
        assert lines.index("*.p8") == lines.index(_TEMPLATE_HEADER) + 1, "under its own header"
        # header moved below a project negation: a fresh block goes on top, above the negation
        new, rules = patch("!build/keep.p8\n" + block, "mobile-app")
        lines = new.splitlines()
        assert lines[0] == _TEMPLATE_HEADER and lines[1] == "*.p8"
        assert lines.index("*.p8") < lines.index("!build/keep.p8")

    def test_fix_backfill_keeps_crlf_line_endings(self, tmp_path):
        proj = _mobile_project(tmp_path / "mob", None)
        (proj / ".gitignore").write_bytes(b".env\r\n*.log\r\n")
        fix_project(proj, project_type="mobile-app")
        raw = (proj / ".gitignore").read_bytes()
        assert b"*.p8\r\n" in raw and b".env\r\n*.log\r\n" in raw
        assert b"\n" not in raw.replace(b"\r\n", b""), "no bare LF line"
        # a MIXED file is written LF, as before this step existed — never every line turned CRLF
        mixed = _mobile_project(tmp_path / "mixed", None)
        (mixed / ".gitignore").write_bytes(b".env\r\n*.log\n")
        fix_project(mixed, project_type="mobile-app")
        assert b"\r" not in (mixed / ".gitignore").read_bytes()
