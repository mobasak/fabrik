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

        monkeypatch.setattr(docs_updater, "FABRIK_ROOT", tmp_path)

        # Try to create stub
        from docs_updater import create_module_stub

        result = create_module_stub(mod)

        assert result is False
        assert "DO NOT OVERWRITE" in existing.read_text()
