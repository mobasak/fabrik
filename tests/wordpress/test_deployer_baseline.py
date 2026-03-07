import dataclasses
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

from fabrik.wordpress.deployer import SiteDeployer

KNOWN_GOOD_HASH = "2f31292fe4ce705d8f45ecd38cb6e8a7f7574dd365ba1e63d107592d0a8ffd4e"


@patch("subprocess.run")
@patch("fabrik.wordpress.stages.dns.DomainSetup")
@patch("fabrik.wordpress.stages.settings.SettingsApplicator")
@patch("fabrik.wordpress.stages.theme.ThemeCustomizer")
@patch("fabrik.wordpress.stages.pages.generate_pages")
@patch("fabrik.wordpress.stages.pages.PageCreator")
@patch("fabrik.wordpress.stages.menus.MenuCreator")
@patch("fabrik.wordpress.stages.forms.FormCreator")
@patch("fabrik.wordpress.stages.seo.SEOApplicator")
@patch("fabrik.wordpress.stages.analytics.AnalyticsInjector")
@patch("fabrik.wordpress.deployer.WordPressClient")
def test_baseline_is_deterministic(
    mock_wp_client,
    mock_analytics,
    mock_seo,
    mock_forms,
    mock_menus,
    mock_pages,
    mock_generate,
    mock_theme,
    mock_settings,
    mock_domain_setup,
    mock_run,
):
    # Mock generate_pages to return empty list (dry-run behavior)
    mock_generate.return_value = []

    with patch.dict(
        os.environ, {"WP_CONTAINER_NAME_OCORON_COM": "ocoron-com-wordpress-1"}, clear=True
    ):
        deployer1 = SiteDeployer("ocoron.com", dry_run=True)
        result1 = deployer1.deploy()

        deployer2 = SiteDeployer("ocoron.com", dry_run=True)
        result2 = deployer2.deploy()

        json1 = json.dumps(dataclasses.asdict(result1), sort_keys=True)
        json2 = json.dumps(dataclasses.asdict(result2), sort_keys=True)

        hash1 = hashlib.sha256(json1.encode()).hexdigest()
        hash2 = hashlib.sha256(json2.encode()).hexdigest()

        assert hash1 == hash2
        assert hash1 == KNOWN_GOOD_HASH


def test_baseline_matches_fixture():
    fixture_path = Path(__file__).parent / "fixtures" / "ocoron_baseline.json"
    with open(fixture_path, "rb") as f:
        content = f.read()

    # Optional: we can load/dump to ensure format consistency
    # But the spec says "Load..., Compute its SHA-256., Assert it equals KNOWN_GOOD_HASH."
    computed_hash = hashlib.sha256(content).hexdigest()
    assert computed_hash == KNOWN_GOOD_HASH
