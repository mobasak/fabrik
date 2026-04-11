"""Tests for T1 (site.yaml) and T2 (compose.dev.yaml, nginx-dev.conf) WordPress scaffold templates."""

import os
from pathlib import Path

import pytest
import yaml

from fabrik.scaffold import create_project
from fabrik.wordpress.spec_loader import SpecLoader
from fabrik.wordpress.spec_validator import SpecValidator

FABRIK_ROOT = Path("/opt/fabrik")
requires_fabrik_env = pytest.mark.skipif(
    not FABRIK_ROOT.exists() or os.getenv("CI") == "true",
    reason="Requires full fabrik environment at /opt/fabrik (not available in CI)",
)


@requires_fabrik_env
class TestWordPressSiteYaml:
    """T1 — Scaffold emits site.yaml into WordPress project folder."""

    def test_site_yaml_created(self, tmp_path: Path) -> None:
        """site.yaml is generated in the project directory."""
        create_project(
            name="t1-test",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        site_yaml = tmp_path / "t1-test" / "site.yaml"
        assert site_yaml.exists(), "site.yaml not created"

    def test_site_yaml_valid_yaml(self, tmp_path: Path) -> None:
        """Rendered site.yaml is valid YAML."""
        create_project(
            name="t1-valid",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        data = yaml.safe_load((tmp_path / "t1-valid" / "site.yaml").read_text())
        assert isinstance(data, dict)

    def test_site_yaml_schema_version(self, tmp_path: Path) -> None:
        """site.yaml has schema_version == 1."""
        create_project(
            name="t1-sv",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        data = yaml.safe_load((tmp_path / "t1-sv" / "site.yaml").read_text())
        assert data["schema_version"] == 1

    def test_site_yaml_site_name(self, tmp_path: Path) -> None:
        """site.yaml site.name matches the project name."""
        create_project(
            name="t1-sn",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        data = yaml.safe_load((tmp_path / "t1-sn" / "site.yaml").read_text())
        assert data["site"]["name"] == "t1-sn"

    def test_site_yaml_site_domain(self, tmp_path: Path) -> None:
        """site.yaml site.domain matches <name>.vps1.ocoron.com."""
        create_project(
            name="t1-sd",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        data = yaml.safe_load((tmp_path / "t1-sd" / "site.yaml").read_text())
        assert data["site"]["domain"] == "t1-sd.vps1.ocoron.com"

    def test_site_yaml_deployment_target(self, tmp_path: Path) -> None:
        """site.yaml deployment.target == 'production'."""
        create_project(
            name="t1-dt",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        data = yaml.safe_load((tmp_path / "t1-dt" / "site.yaml").read_text())
        assert data["deployment"]["target"] == "production"

    def test_site_yaml_default_preset_saas(self, tmp_path: Path) -> None:
        """site.yaml defaults to saas preset."""
        create_project(
            name="t1-saas",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        data = yaml.safe_load((tmp_path / "t1-saas" / "site.yaml").read_text())
        assert data["preset"] == "saas"

    def test_site_yaml_custom_preset(self, tmp_path: Path) -> None:
        """site.yaml respects --preset argument."""
        create_project(
            name="t1-company",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
            preset="company",
        )
        data = yaml.safe_load((tmp_path / "t1-company" / "site.yaml").read_text())
        assert data["preset"] == "company"

    def test_site_yaml_no_raw_jinja(self, tmp_path: Path) -> None:
        """Rendered site.yaml has no unresolved Jinja syntax."""
        create_project(
            name="t1-jinja",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        content = (tmp_path / "t1-jinja" / "site.yaml").read_text()
        assert "{{" not in content
        assert "}}" not in content

    def test_gitignore_contains_site_yaml(self, tmp_path: Path) -> None:
        """WordPress .gitignore includes site.yaml."""
        create_project(
            name="t1-gi",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        content = (tmp_path / "t1-gi" / ".gitignore").read_text()
        assert "site.yaml\n" in content

    def test_site_yaml_passes_spec_validator(self, tmp_path: Path) -> None:
        """Scaffolded site.yaml loads through SpecLoader and passes SpecValidator required fields."""
        create_project(
            name="t1-validate",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        site_yaml_path = tmp_path / "t1-validate" / "site.yaml"
        loader = SpecLoader("t1-validate", site_path=site_yaml_path)
        spec = loader.load()
        validator = SpecValidator(spec)
        errors, _warnings = validator.validate()
        # Filter to required-field and type errors only (locale mismatches from
        # preset translations are expected when the site declares fewer languages)
        required_errors = [e for e in errors if not e.endswith("not in languages list")]
        assert required_errors == [], f"SpecValidator required-field errors: {required_errors}"


@requires_fabrik_env
class TestWordPressComposeDevYaml:
    """T2 — Scaffold emits compose.dev.yaml into WordPress project folder."""

    def test_compose_dev_created(self, tmp_path: Path) -> None:
        """compose.dev.yaml is generated in the project directory."""
        create_project(
            name="t2-test",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        assert (tmp_path / "t2-test" / "compose.dev.yaml").exists()

    def test_compose_dev_valid_yaml(self, tmp_path: Path) -> None:
        """Rendered compose.dev.yaml is valid YAML."""
        create_project(
            name="t2-yaml",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        data = yaml.safe_load((tmp_path / "t2-yaml" / "compose.dev.yaml").read_text())
        assert "services" in data

    def test_compose_dev_database_name(self, tmp_path: Path) -> None:
        """compose.dev.yaml uses underscored project name for database."""
        create_project(
            name="t2-db-test",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        content = (tmp_path / "t2-db-test" / "compose.dev.yaml").read_text()
        assert "t2_db_test_db" in content

    def test_compose_dev_default_port(self, tmp_path: Path) -> None:
        """compose.dev.yaml uses port 8080 by default."""
        create_project(
            name="t2-port",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        content = (tmp_path / "t2-port" / "compose.dev.yaml").read_text()
        assert "8080:80" in content

    def test_compose_dev_custom_port(self, tmp_path: Path) -> None:
        """compose.dev.yaml respects --dev-port argument."""
        create_project(
            name="t2-cport",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
            dev_port="8090",
        )
        content = (tmp_path / "t2-cport" / "compose.dev.yaml").read_text()
        assert "8090:80" in content

    def test_compose_dev_no_traefik(self, tmp_path: Path) -> None:
        """compose.dev.yaml has no Traefik labels."""
        create_project(
            name="t2-notr",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        content = (tmp_path / "t2-notr" / "compose.dev.yaml").read_text()
        assert "traefik" not in content.lower()

    def test_compose_dev_no_coolify(self, tmp_path: Path) -> None:
        """compose.dev.yaml has no coolify network."""
        create_project(
            name="t2-nocf",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        content = (tmp_path / "t2-nocf" / "compose.dev.yaml").read_text()
        assert "coolify" not in content.lower()

    def test_compose_dev_no_raw_jinja(self, tmp_path: Path) -> None:
        """Rendered compose.dev.yaml has no unresolved Jinja syntax."""
        create_project(
            name="t2-nj",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        content = (tmp_path / "t2-nj" / "compose.dev.yaml").read_text()
        assert "{{" not in content
        assert "}}" not in content

    def test_compose_dev_wp_html_named_volume(self, tmp_path: Path) -> None:
        """compose.dev.yaml declares a named volume for the full WordPress html tree."""
        create_project(
            name="t2-vol",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        data = yaml.safe_load((tmp_path / "t2-vol" / "compose.dev.yaml").read_text())
        assert "wp_html" in data.get("volumes", {}), "wp_html named volume not declared"

    def test_compose_dev_nginx_mounts_themes_plugins(self, tmp_path: Path) -> None:
        """nginx service mounts ./themes and ./plugins for live edits."""
        create_project(
            name="t2-ngm",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        data = yaml.safe_load((tmp_path / "t2-ngm" / "compose.dev.yaml").read_text())
        nginx_volumes = data["services"]["nginx"]["volumes"]
        volume_strs = [str(v) for v in nginx_volumes]
        assert any("./themes:" in v for v in volume_strs), "nginx missing ./themes mount"
        assert any("./plugins:" in v for v in volume_strs), "nginx missing ./plugins mount"

    def test_compose_dev_wordpress_mounts_themes_plugins(self, tmp_path: Path) -> None:
        """wordpress service mounts ./themes and ./plugins for live edits."""
        create_project(
            name="t2-wpm",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        data = yaml.safe_load((tmp_path / "t2-wpm" / "compose.dev.yaml").read_text())
        wp_volumes = data["services"]["wordpress"]["volumes"]
        volume_strs = [str(v) for v in wp_volumes]
        assert any("./themes:" in v for v in volume_strs), "wordpress missing ./themes mount"
        assert any("./plugins:" in v for v in volume_strs), "wordpress missing ./plugins mount"


@requires_fabrik_env
class TestWordPressNginxDevConf:
    """T2 — Scaffold emits nginx-dev.conf into WordPress project folder."""

    def test_nginx_dev_created(self, tmp_path: Path) -> None:
        """nginx-dev.conf is generated in config/ subdirectory."""
        create_project(
            name="t2-ng",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        assert (tmp_path / "t2-ng" / "config" / "nginx-dev.conf").exists()

    def test_nginx_dev_fastcgi_pass(self, tmp_path: Path) -> None:
        """nginx-dev.conf contains fastcgi_pass php."""
        create_project(
            name="t2-fp",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        content = (tmp_path / "t2-fp" / "config" / "nginx-dev.conf").read_text()
        assert "fastcgi_pass php" in content

    def test_nginx_dev_upstream(self, tmp_path: Path) -> None:
        """nginx-dev.conf contains upstream php pointing to wordpress:9000."""
        create_project(
            name="t2-up",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        content = (tmp_path / "t2-up" / "config" / "nginx-dev.conf").read_text()
        assert "server wordpress:9000" in content

    def test_nginx_dev_no_fastcgi_cache(self, tmp_path: Path) -> None:
        """nginx-dev.conf does not include fastcgi_cache."""
        create_project(
            name="t2-nc",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        content = (tmp_path / "t2-nc" / "config" / "nginx-dev.conf").read_text()
        assert "fastcgi_cache" not in content

    def test_nginx_dev_php_location_does_not_block_fpm_passthrough(self, tmp_path: Path) -> None:
        """nginx-dev.conf omits the PHP try_files directive that broke FPM passthrough."""
        create_project(
            name="t2-no-try-files",
            project_type="wordpress",
            description="Test site",
            base=tmp_path,
        )
        content = (tmp_path / "t2-no-try-files" / "config" / "nginx-dev.conf").read_text()
        assert "try_files $uri =404" not in content
