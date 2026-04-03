"""Tests for final_gate.py check_symlinks() governance isolation.

Covers .windsurf/rules/ and .windsurf/workflows/ recursive symlink detection.
"""

from unittest.mock import patch

import pytest


@pytest.fixture()
def fake_project(tmp_path):
    """Create a minimal fake project with governance files as real copies."""
    project = tmp_path / "my-project"
    project.mkdir()

    # Governance files (real copies)
    (project / "AGENTS.md").write_text("# AGENTS\n")
    (project / "AGENTS-compact.md").write_text("# Compact\n")
    (project / "opencode.json").write_text("{}\n")
    (project / ".windsurfrules").write_text("# rules\n")

    # .windsurf/rules/ with a real file
    rules_dir = project / ".windsurf" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "10-python.md").write_text("# Python rules\n")

    # .windsurf/workflows/ with a real file
    workflows_dir = project / ".windsurf" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "deploy.md").write_text("# Deploy workflow\n")

    return project


class TestCheckSymlinksWorkflowsIsolation:
    """Test that check_symlinks() detects symlinks inside .windsurf/workflows/."""

    def test_real_copies_pass(self, fake_project):
        """All real local copies should pass isolation check."""
        import scripts.final_gate as gate

        with patch.object(gate, "FABRIK_ROOT", fake_project):
            passed, msg = gate.check_symlinks()

        assert passed, f"Expected pass but got: {msg}"

    def test_symlinked_workflow_file_fails(self, fake_project, tmp_path):
        """A symlinked file inside .windsurf/workflows/ should fail."""
        import scripts.final_gate as gate

        # Create a file outside the project to symlink to
        external = tmp_path / "external"
        external.mkdir()
        (external / "evil.md").write_text("# external\n")

        # Replace a workflow file with a symlink
        target = fake_project / ".windsurf" / "workflows" / "deploy.md"
        target.unlink()
        target.symlink_to(external / "evil.md")

        with patch.object(gate, "FABRIK_ROOT", fake_project):
            passed, msg = gate.check_symlinks()

        assert not passed, "Expected failure for symlinked workflow file"
        assert "workflows" in msg
        assert "symlink" in msg

    def test_symlinked_workflow_pointing_to_external_fails(self, fake_project, tmp_path):
        """A symlink pointing to an external path should report isolation broken."""
        import scripts.final_gate as gate

        external = tmp_path / "external"
        external.mkdir()
        (external / "real.md").write_text("# real\n")

        target = fake_project / ".windsurf" / "workflows" / "deploy.md"
        target.unlink()
        target.symlink_to(external / "real.md")

        with patch.object(gate, "FABRIK_ROOT", fake_project):
            passed, msg = gate.check_symlinks()

        assert not passed, "Expected failure for symlinked workflow file"
        assert "symlink" in msg

    def test_symlinked_rules_file_still_detected(self, fake_project, tmp_path):
        """Ensure rules/ recursive check still works alongside workflows/."""
        import scripts.final_gate as gate

        external = tmp_path / "external"
        external.mkdir()
        (external / "bad-rule.md").write_text("# bad\n")

        # Add a symlink inside rules/
        symlink_path = fake_project / ".windsurf" / "rules" / "99-bad.md"
        symlink_path.symlink_to(external / "bad-rule.md")

        with patch.object(gate, "FABRIK_ROOT", fake_project):
            passed, msg = gate.check_symlinks()

        assert not passed, "Expected failure for symlinked rule file"
        assert "rules" in msg
        assert "symlink" in msg

    def test_workflows_dir_itself_as_symlink_fails(self, fake_project, tmp_path):
        """The .windsurf/workflows/ directory itself being a symlink should fail."""
        import shutil

        import scripts.final_gate as gate

        external_wf = tmp_path / "external_workflows"
        external_wf.mkdir()
        (external_wf / "deploy.md").write_text("# deploy\n")

        # Replace workflows dir with symlink
        wf_dir = fake_project / ".windsurf" / "workflows"
        shutil.rmtree(wf_dir)
        wf_dir.symlink_to(external_wf)

        with patch.object(gate, "FABRIK_ROOT", fake_project):
            passed, msg = gate.check_symlinks()

        assert not passed, "Expected failure for symlinked workflows directory"
        assert "workflows" in msg
