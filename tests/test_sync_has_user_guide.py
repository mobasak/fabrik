"""Regression tests: has_user_guide survives the sync_projects pipeline.

Scaffolds one guide-enabled and one non-guide project, runs _build_project()
+ save_registry(), and asserts data/projects.yaml preserves the correct values.
"""

import pytest
import yaml

from fabrik.scaffold import create_project

# Avoid running outside Fabrik dev environment
pytestmark = pytest.mark.skipif(
    not __import__("pathlib").Path("/opt/fabrik/src/fabrik").is_dir(),
    reason="Requires Fabrik environment",
)


@pytest.fixture()
def scaffold_pair(tmp_path):
    """Scaffold one guide-enabled project and one non-guide project."""
    # static-site is guide-enabled per GUIDE_ENABLED_TYPES
    # (saas-skeleton was removed in commit f557c35, 2026-04-15)
    create_project(
        name="guide-proj",
        project_type="static-site",
        description="Guide-enabled project",
        base=tmp_path,
    )
    create_project(
        name="noguide-proj",
        project_type="python-api",
        description="Non-guide project",
        base=tmp_path,
    )
    return tmp_path


class TestSyncHasUserGuide:
    """Verify has_user_guide round-trips through sync_projects pipeline."""

    def test_build_project_preserves_has_user_guide(self, scaffold_pair):
        """_build_project() reads has_user_guide from project.yaml."""
        from scripts.sync_projects import _build_project

        guide_proj = _build_project(scaffold_pair / "guide-proj")
        noguide_proj = _build_project(scaffold_pair / "noguide-proj")

        assert guide_proj.has_user_guide is True, "guide-enabled type should be True"
        assert noguide_proj.has_user_guide is False, "non-guide type should be False"

    def test_to_registry_dict_emits_has_user_guide(self, scaffold_pair):
        """to_registry_dict() includes has_user_guide in output."""
        from scripts.sync_projects import _build_project

        guide_proj = _build_project(scaffold_pair / "guide-proj")
        noguide_proj = _build_project(scaffold_pair / "noguide-proj")

        guide_dict = guide_proj.to_registry_dict()
        noguide_dict = noguide_proj.to_registry_dict()

        assert "has_user_guide" in guide_dict
        assert guide_dict["has_user_guide"] is True
        assert "has_user_guide" in noguide_dict
        assert noguide_dict["has_user_guide"] is False

    def test_save_registry_persists_has_user_guide(self, scaffold_pair, tmp_path):
        """Full pipeline: scaffold → _build_project → save_registry → read YAML."""
        from scripts.sync_projects import _build_project, save_registry

        projects = [
            _build_project(scaffold_pair / "guide-proj"),
            _build_project(scaffold_pair / "noguide-proj"),
        ]

        # Write to a temp registry path instead of the real one
        registry_path = tmp_path / "data" / "projects.yaml"
        registry_path.parent.mkdir(parents=True, exist_ok=True)

        import scripts.sync_projects as sp

        original_root = sp.FABRIK_ROOT
        try:
            sp.FABRIK_ROOT = tmp_path
            save_registry(projects)
        finally:
            sp.FABRIK_ROOT = original_root

        assert registry_path.exists(), "Registry file should be created"
        data = yaml.safe_load(registry_path.read_text())
        projects_data = data["projects"]

        assert projects_data["guide-proj"]["has_user_guide"] is True
        assert projects_data["noguide-proj"]["has_user_guide"] is False


class TestRegistryHasUserGuide:
    """Verify registry.py round-trips has_user_guide."""

    def test_to_dict_emits_has_user_guide(self):
        """Project.to_dict() includes has_user_guide."""
        from fabrik.registry import Project

        p_true = Project(name="a", path="/opt/a", has_user_guide=True)
        p_false = Project(name="b", path="/opt/b", has_user_guide=False)

        assert p_true.to_dict()["has_user_guide"] is True
        assert p_false.to_dict()["has_user_guide"] is False

    def test_from_dict_reads_has_user_guide(self):
        """Project.from_dict() restores has_user_guide."""
        from fabrik.registry import Project

        p = Project.from_dict("x", {"path": "/opt/x", "has_user_guide": True})
        assert p.has_user_guide is True

        p2 = Project.from_dict("y", {"path": "/opt/y"})
        assert p2.has_user_guide is False
