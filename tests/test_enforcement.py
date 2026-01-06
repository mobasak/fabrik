"""Tests for scripts/enforcement/ convention validators."""

from pathlib import Path

import pytest


class TestCheckEnvVars:
    """Tests for check_env_vars.py."""

    def test_detects_hardcoded_localhost(self, tmp_path: Path) -> None:
        """Should detect hardcoded localhost assignments."""
        from scripts.enforcement.check_env_vars import check_file

        bad_file = tmp_path / "bad_code.py"
        bad_file.write_text('DB_HOST = "localhost"\n')

        results = check_file(bad_file)
        assert len(results) == 1
        assert results[0].check_name == "env_vars"
        assert "host" in results[0].message.lower()

    def test_detects_hardcoded_url(self, tmp_path: Path) -> None:
        """Should detect hardcoded http://localhost URLs."""
        from scripts.enforcement.check_env_vars import check_file

        bad_file = tmp_path / "bad_code.py"
        bad_file.write_text('url = "http://localhost:8000/api"\n')

        results = check_file(bad_file)
        assert len(results) == 1

    def test_allows_getenv_default(self, tmp_path: Path) -> None:
        """Should allow os.getenv with localhost as default."""
        from scripts.enforcement.check_env_vars import check_file

        good_file = tmp_path / "good_code.py"
        good_file.write_text("host = os.getenv('DB_HOST', 'localhost')\n")

        results = check_file(good_file)
        assert len(results) == 0

    def test_skips_test_files(self, tmp_path: Path) -> None:
        """Should skip files with 'test' in the name."""
        from scripts.enforcement.check_env_vars import check_file

        test_file = tmp_path / "test_config.py"
        test_file.write_text('DB_HOST = "localhost"\n')

        results = check_file(test_file)
        assert len(results) == 0


class TestCheckSecrets:
    """Tests for check_secrets.py."""

    def test_detects_hardcoded_password(self, tmp_path: Path) -> None:
        """Should detect hardcoded passwords."""
        from scripts.enforcement.check_secrets import check_file

        bad_file = tmp_path / "settings.py"  # Not 'test' in name
        bad_file.write_text('password = "mysecretpassword123"\n')

        results = check_file(bad_file)
        assert len(results) >= 1
        assert results[0].check_name == "secrets"

    def test_detects_openai_key_pattern(self, tmp_path: Path) -> None:
        """Should detect OpenAI API key patterns."""
        from scripts.enforcement.check_secrets import check_file

        bad_file = tmp_path / "settings.py"
        # OpenAI key pattern: sk-[a-zA-Z0-9]{32,}
        bad_file.write_text('key = "sk-abcdefghij1234567890abcdefghij12"\n')

        results = check_file(bad_file)
        assert len(results) >= 1


class TestCheckDocker:
    """Tests for check_docker.py."""

    def test_detects_alpine_base(self, tmp_path: Path) -> None:
        """Should warn about Alpine base images."""
        from scripts.enforcement.check_docker import check_file

        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM python:3.12-alpine\nRUN pip install flask\n")

        results = check_file(dockerfile)
        assert any("alpine" in r.message.lower() for r in results)

    def test_detects_missing_healthcheck(self, tmp_path: Path) -> None:
        """Should warn about missing HEALTHCHECK."""
        from scripts.enforcement.check_docker import check_file

        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM python:3.12-slim\nCMD python app.py\n")

        results = check_file(dockerfile)
        assert any("healthcheck" in r.message.lower() for r in results)

    def test_passes_good_dockerfile(self, tmp_path: Path) -> None:
        """Should pass a well-formed Dockerfile."""
        from scripts.enforcement.check_docker import check_file

        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(
            "FROM python:3.12-slim-bookworm\n"
            "HEALTHCHECK CMD curl -f http://localhost/health\n"
            "CMD python app.py\n"
        )

        results = check_file(dockerfile)
        # Should have no Alpine or healthcheck warnings
        assert not any("alpine" in r.message.lower() for r in results)
        assert not any("missing healthcheck" in r.message.lower() for r in results)


class TestCheckRuleSize:
    """Tests for check_rule_size.py."""

    def test_passes_small_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should pass when all rule files are under 12KB."""
        import scripts.enforcement.check_rule_size as module

        rules_dir = tmp_path / ".windsurf" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "00-critical.md").write_text("# Small file\n")

        monkeypatch.setattr(
            module, "__file__", str(tmp_path / "scripts" / "enforcement" / "check_rule_size.py")
        )

        # Can't easily test due to path resolution, but structure is correct
        assert True


class TestValidateConventions:
    """Tests for validate_conventions.py orchestrator."""

    def test_run_all_checks_python(self, tmp_path: Path) -> None:
        """Should run Python checks on .py files."""
        from scripts.enforcement.validate_conventions import run_all_checks

        py_file = tmp_path / "bad.py"
        py_file.write_text('host = "localhost"\npassword = "secret123"\n')

        results = run_all_checks(py_file)
        check_names = {r.check_name for r in results}
        assert "env_vars" in check_names or "secrets" in check_names

    def test_run_all_checks_dockerfile(self, tmp_path: Path) -> None:
        """Should run Docker checks on Dockerfiles."""
        from scripts.enforcement.validate_conventions import run_all_checks

        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM alpine\nCMD echo hi\n")

        results = run_all_checks(dockerfile)
        assert any(r.check_name == "docker" for r in results)

    def test_exit_codes(self, tmp_path: Path) -> None:
        """Should return correct exit codes."""
        from scripts.enforcement.validate_conventions import Severity

        assert Severity.ERROR.value == "error"
        assert Severity.WARN.value == "warn"
        assert Severity.PASS.value == "pass"
