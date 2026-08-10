"""Tests for docs_updater.py documentation automation features."""

# Import the module functions
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from docs_updater import (
    PLANS_BLOCK_RE,
    STRUCTURE_BLOCK_RE,
    extract_block_body,
    generate_plans_table,
    is_public_module,
    replace_block,
)


class TestBoundedBlockReplacement:
    """Tests for bounded block replacement (idempotency)."""

    def test_replace_block_changes_when_body_differs(self):
        """Block should be replaced when body content changes."""
        text = """# Header

<!-- AUTO-GENERATED:STRUCTURE:START -->
<!-- AUTO-GENERATED:STRUCTURE v1 | 2026-01-01T00:00Z -->
old content
<!-- AUTO-GENERATED:STRUCTURE:END -->

# Footer
"""
        new_body = "new content"
        result, changed = replace_block(text, new_body, STRUCTURE_BLOCK_RE, "STRUCTURE")

        assert changed is True
        assert "new content" in result
        assert "old content" not in result

    def test_replace_block_idempotent_when_body_same(self):
        """Block should NOT be replaced when body content is identical."""
        text = """# Header

<!-- AUTO-GENERATED:STRUCTURE:START -->
<!-- AUTO-GENERATED:STRUCTURE v1 | 2026-01-01T00:00Z -->
same content
<!-- AUTO-GENERATED:STRUCTURE:END -->

# Footer
"""
        new_body = "same content"
        result, changed = replace_block(text, new_body, STRUCTURE_BLOCK_RE, "STRUCTURE")

        assert changed is False
        assert result == text  # Unchanged

    def test_extract_block_body_excludes_markers(self):
        """Extracted body should not include HTML comment markers."""
        text = """<!-- AUTO-GENERATED:PLANS:START -->
<!-- AUTO-GENERATED:PLANS v1 | 2026-01-01T00:00Z -->
| Plan | Date |
|------|------|
<!-- AUTO-GENERATED:PLANS:END -->"""

        body = extract_block_body(text, PLANS_BLOCK_RE)

        assert body is not None
        assert "<!--" not in body
        assert "| Plan | Date |" in body


class TestPublicModuleDetection:
    """Tests for public module detection."""

    def test_is_public_module_with_all(self, tmp_path):
        """Module with __all__ should be detected as public."""
        mod = tmp_path / "mymodule"
        mod.mkdir()
        (mod / "__init__.py").write_text("__all__ = ['foo', 'bar']")

        assert is_public_module(mod) is True

    def test_is_public_module_with_readme(self, tmp_path):
        """Module with README.md should be detected as public."""
        mod = tmp_path / "mymodule"
        mod.mkdir()
        (mod / "__init__.py").write_text("# empty")
        (mod / "README.md").write_text("# My Module")

        assert is_public_module(mod) is True

    def test_is_public_module_without_markers(self, tmp_path):
        """Module without __all__ or README should NOT be detected as public."""
        mod = tmp_path / "mymodule"
        mod.mkdir()
        (mod / "__init__.py").write_text("# internal module")

        assert is_public_module(mod) is False

    def test_is_public_module_without_init(self, tmp_path):
        """Directory without __init__.py should NOT be detected as module."""
        mod = tmp_path / "notamodule"
        mod.mkdir()

        assert is_public_module(mod) is False


class TestPlansTableGeneration:
    """Tests for plans table generation."""

    def test_generate_plans_table_empty(self, tmp_path, monkeypatch):
        """Empty plans directory should generate placeholder table."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()

        # Monkeypatch PLANS_DIR
        import docs_updater

        monkeypatch.setattr(docs_updater, "PLANS_DIR", plans_dir)

        table = generate_plans_table()

        assert "(none)" in table
        assert "| Plan | Date | Status |" in table

    def test_generate_plans_table_with_files(self, tmp_path, monkeypatch):
        """Plans directory with files should generate proper table."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        (plans_dir / "2026-01-07-test-plan.md").write_text("# Test Plan")

        # Monkeypatch PLANS_DIR
        import docs_updater

        monkeypatch.setattr(docs_updater, "PLANS_DIR", plans_dir)

        table = generate_plans_table()

        assert "2026-01-07-test-plan.md" in table
        assert "2026-01-07" in table
        assert "Active" in table


class TestStubCreation:
    """Tests for module stub creation."""

    def test_stub_creation_skips_existing(self, tmp_path, monkeypatch):
        """Existing docs should NOT be overwritten."""
        import docs_updater

        # Setup
        ref_dir = tmp_path / "docs" / "reference"
        ref_dir.mkdir(parents=True)
        existing = ref_dir / "mymodule.md"
        existing.write_text("# Existing content - DO NOT OVERWRITE")

        mod = tmp_path / "src" / "fabrik" / "mymodule"
        mod.mkdir(parents=True)
        (mod / "__init__.py").write_text("__all__ = ['foo']")

        monkeypatch.setattr(docs_updater, "PROJECT_ROOT", tmp_path)

        # Try to create stub
        from docs_updater import create_module_stub

        result = create_module_stub(mod)

        assert result is False
        assert "DO NOT OVERWRITE" in existing.read_text()


class TestSyncedDocsAreNotLinkChecked:
    """Fabrik-synced governance/reference copies are gitignored in consuming projects and their
    links resolve only in the repo that OWNS them (`scripts/kilo-benchmarks/*`,
    `docs/workflows/*`). Checking them against a consuming project reported broken links no
    project could fix and blocked /fabrik-release, whose preconditions require this check green.
    Reported from tryton-crm 2026-08-10 with 4 such rows.
    """

    @staticmethod
    def _repo(tmp_path, *, ignore_line: str) -> Path:
        import subprocess
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        (tmp_path / ".gitignore").write_text(ignore_line + "\n")
        synced = tmp_path / "docs" / "reference" / "kilo"
        synced.mkdir(parents=True)
        (synced / "BENCHMARK_SOURCES.md").write_text(
            "# Sources\n\n[tool](../../../scripts/kilo-benchmarks/update_kilo_benchmarks.py)\n"
        )
        owned = tmp_path / "docs"
        (owned / "OWNED.md").write_text("# Owned\n\n[gone](../scripts/does_not_exist.py)\n")
        return tmp_path

    def test_a_gitignored_synced_doc_is_skipped(self, tmp_path, monkeypatch):
        root = self._repo(tmp_path, ignore_line="docs/reference/kilo/")
        monkeypatch.chdir(root)
        import docs_updater as du
        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        issues = du.check_link_integrity()
        assert not any("BENCHMARK_SOURCES" in i for i in issues), issues

    def test_a_tracked_doc_with_a_broken_link_is_still_reported(self, tmp_path, monkeypatch):
        """Non-vacuity: the skip must be the gitignore predicate, not 'stop checking links'."""
        root = self._repo(tmp_path, ignore_line="docs/reference/kilo/")
        monkeypatch.chdir(root)
        import docs_updater as du
        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        issues = du.check_link_integrity()
        assert any("OWNED.md" in i for i in issues), f"a repo-owned broken link must still fail: {issues}"

    def test_when_nothing_is_ignored_the_synced_doc_is_checked(self, tmp_path, monkeypatch):
        """The hub owns these files (tracked there), so it must keep checking them — that is
        where a genuinely broken link can actually be fixed."""
        root = self._repo(tmp_path, ignore_line="# nothing ignored")
        monkeypatch.chdir(root)
        import docs_updater as du
        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        issues = du.check_link_integrity()
        assert any("BENCHMARK_SOURCES" in i for i in issues), issues

    def test_git_failure_falls_back_to_checking_everything(self, tmp_path, monkeypatch):
        """A visible false positive beats silently skipping a doc the project really owns."""
        import docs_updater as du
        monkeypatch.setattr(du.subprocess, "run",
                            lambda *a, **k: (_ for _ in ()).throw(OSError("no git")))
        assert du._gitignored([tmp_path / "docs" / "x.md"]) == set()
