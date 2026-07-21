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
        (project_dir / ".windsurfrules").touch()

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
        (project_dir / ".windsurfrules").touch()

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
        (project_dir / ".windsurfrules").touch()

        results = scan_health(root=tmp_path)

        assert len(results) == 0
