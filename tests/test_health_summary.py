from pathlib import Path

from scripts.health_summary import scan_health


class TestScanHealth:
    def test_detects_missing_file(self, tmp_path: Path):
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()

        # Create all except AGENTS.md
        (project_dir / ".env.example").touch()
        (project_dir / "project.yaml").touch()
        (project_dir / "compose.yaml").touch()
        (project_dir / "Dockerfile").touch()

        results = scan_health(root=tmp_path)

        assert len(results) == 1
        result = results[0]
        assert result["project"] == "my-project"
        assert "AGENTS.md" in result["missing"]
        assert result["status"] != "healthy"

    def test_healthy_project(self, tmp_path: Path):
        project_dir = tmp_path / "healthy-project"
        project_dir.mkdir()

        # Create all essential files
        (project_dir / "AGENTS.md").touch()
        (project_dir / ".env.example").touch()
        (project_dir / "project.yaml").touch()
        (project_dir / "compose.yaml").touch()
        (project_dir / "Dockerfile").touch()

        results = scan_health(root=tmp_path)

        assert len(results) == 1
        result = results[0]
        assert result["project"] == "healthy-project"
        assert result["status"] == "healthy"
        assert result["missing"] == []

    def test_skips_excluded_directories(self, tmp_path: Path):
        # Create a directory named 'fabrik' which matches _is_excluded
        project_dir = tmp_path / "fabrik"
        project_dir.mkdir()

        # Create all essential files just in case it were scanned
        (project_dir / "AGENTS.md").touch()
        (project_dir / ".env.example").touch()
        (project_dir / "project.yaml").touch()
        (project_dir / "compose.yaml").touch()
        (project_dir / "Dockerfile").touch()

        results = scan_health(root=tmp_path)

        assert len(results) == 0


def test_a_project_without_the_retired_windsurfrules_is_healthy(tmp_path: Path) -> None:
    """D-529: the sync prunes `.windsurfrules` from every project, so its absence is the
    expected state and must not count as a missing essential file."""
    project_dir = tmp_path / "pruned-project"
    project_dir.mkdir()
    for name in ("AGENTS.md", ".env.example", "project.yaml", "compose.yaml", "Dockerfile"):
        (project_dir / name).touch()
    [result] = [r for r in scan_health(root=tmp_path) if r["project"] == "pruned-project"]
    assert result["missing"] == [] and result["status"] == "healthy", result
