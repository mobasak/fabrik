"""
Tests for WordPress deployment idempotency.

Ensures that:
- Consecutive identical runs skip all stages on second run
- Changing one spec key re-runs only affected stages
- Atomic write survives mid-write failure
- --force-stage bypasses skip for named stage
"""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pytest

from fabrik.wordpress.deployer import SiteDeployer
from fabrik.wordpress.planner import STAGE_KEYS, Planner
from fabrik.wordpress.stages import StageResult


@pytest.fixture
def mock_spec():
    """Return a minimal valid spec dict."""
    return {
        "schema_version": 1,
        "site": {"domain": "test.com", "name": "Test Site"},
        "brand": {"name": "Test Brand"},
        "deployment": {"vps_ip": "1.2.3.4", "target": "coolify"},
        "languages": {"primary": "en_US", "list": ["en_US"]},
        "theme": {"slug": "twentytwentyfour"},
        "plugins": {"base": ["contact-form-7"]},
        "preset": "saas",
        "pages": [{"id": "home", "title": "Home"}],
        "navigation": {"main": [{"label": "Home", "page_id": "home"}]},
        "contact": {"email": "test@test.com"},
        "forms": [],
        "seo": {"site_name": "Test"},
        "analytics": {"google_analytics_id": "UA-123"},
    }


@pytest.fixture
def mock_stage_apply():
    """Patch all stage apply functions to return success."""
    stage_names = list(STAGE_KEYS.keys())
    patches = {}
    mocks = {}

    for stage_name in stage_names:
        module_path = f"fabrik.wordpress.stages.{stage_name}"
        patcher = patch(f"{module_path}.apply")
        patches[stage_name] = patcher
        mock = patcher.start()
        # Return successful StageResult
        mock.return_value = StageResult(name=stage_name, success=True, skipped=False)
        mocks[stage_name] = mock

    yield mocks

    # Cleanup
    for patcher in patches.values():
        patcher.stop()


@pytest.fixture
def mock_resolved_spec(mock_spec):
    """Mock ResolvedSpec.from_site to return test spec."""
    with patch("fabrik.wordpress.resolved_spec.ResolvedSpec.from_site") as mock:
        from fabrik.wordpress.resolved_spec import ResolvedSpec

        # Create a real ResolvedSpec instance with test data
        resolved = ResolvedSpec(site_id="test.com", data=mock_spec)
        mock.return_value = resolved
        yield mock


@pytest.fixture
def mock_wordpress_client():
    """Mock get_wordpress_client to avoid real WordPress connections."""
    with patch("fabrik.wordpress.deployer.get_wordpress_client") as mock:
        client = Mock()
        client.rewrite_flush = Mock()
        client.cache_flush = Mock()
        mock.return_value = client
        yield mock


def test_consecutive_identical_runs_skip_stages(
    tmp_path, mock_spec, mock_stage_apply, mock_resolved_spec, mock_wordpress_client
):
    """Test that consecutive identical runs skip all stages on second run."""
    # Setup build directory with pre-populated plan
    build_dir = tmp_path / "build" / "sites" / "test.com"
    build_dir.mkdir(parents=True)

    dummy_spec_path = tmp_path / "site.yaml"

    # Patch BUILD_ROOT to use tmp_path
    with patch("fabrik.wordpress.planner.BUILD_ROOT", tmp_path / "build" / "sites"), \
         patch("fabrik.wordpress.deployer.BUILD_ROOT", tmp_path / "build" / "sites"), \
         patch("fabrik.wordpress.planner.resolve_spec_path", return_value=(dummy_spec_path, False)), \
         patch("fabrik.wordpress.deployer.resolve_spec_path", return_value=(dummy_spec_path, False)), \
         patch("fabrik.wordpress.deployer.load_spec_from_path", return_value=mock_spec):
                # First run: generate plan
                planner = Planner("test.com")
                planner.plan()

                # First deploy
                deployer1 = SiteDeployer("test.com", dry_run=False)
                result1 = deployer1.deploy()

                assert result1.success
                # All stages should run (not skipped)
                assert len(result1.steps_completed) > 0

                # Get call counts from first run
                first_run_calls = {name: mock.call_count for name, mock in mock_stage_apply.items()}

                # Second deploy (no spec changes)
                deployer2 = SiteDeployer("test.com", dry_run=False)
                result2 = deployer2.deploy()

                assert result2.success
                # No additional stage apply calls (all skipped)
                for name, mock in mock_stage_apply.items():
                    assert mock.call_count == first_run_calls[name], (
                        f"Stage {name} was called again on second run"
                    )


def test_changing_spec_reruns_affected_stages(
    tmp_path, mock_spec, mock_stage_apply, mock_resolved_spec, mock_wordpress_client
):
    """Test that changing one spec key re-runs only affected stages."""
    build_dir = tmp_path / "build" / "sites" / "test.com"
    build_dir.mkdir(parents=True)

    dummy_spec_path = tmp_path / "site.yaml"

    with patch("fabrik.wordpress.planner.BUILD_ROOT", tmp_path / "build" / "sites"), \
         patch("fabrik.wordpress.deployer.BUILD_ROOT", tmp_path / "build" / "sites"), \
         patch("fabrik.wordpress.planner.resolve_spec_path", return_value=(dummy_spec_path, False)), \
         patch("fabrik.wordpress.deployer.resolve_spec_path", return_value=(dummy_spec_path, False)), \
         patch("fabrik.wordpress.deployer.load_spec_from_path", return_value=mock_spec):
                # First run
                planner = Planner("test.com")
                planner.plan()

                deployer1 = SiteDeployer("test.com", dry_run=False)
                result1 = deployer1.deploy()
                assert result1.success

                first_run_calls = {name: mock.call_count for name, mock in mock_stage_apply.items()}

    # Modify spec to change seo key only
    modified_spec = mock_spec.copy()
    modified_spec["seo"] = {"site_name": "Test", "ga4_id": "G-999"}

    with patch("fabrik.wordpress.planner.BUILD_ROOT", tmp_path / "build" / "sites"), \
         patch("fabrik.wordpress.deployer.BUILD_ROOT", tmp_path / "build" / "sites"), \
         patch("fabrik.wordpress.planner.resolve_spec_path", return_value=(dummy_spec_path, False)), \
         patch("fabrik.wordpress.deployer.resolve_spec_path", return_value=(dummy_spec_path, False)), \
         patch("fabrik.wordpress.deployer.load_spec_from_path", return_value=modified_spec):
                    # Update resolved spec mock to return modified version
                    from fabrik.wordpress.resolved_spec import ResolvedSpec

                    modified_resolved = ResolvedSpec(site_id="test.com", data=modified_spec)
                    mock_resolved_spec.return_value = modified_resolved

                    # Re-plan with modified spec
                    planner2 = Planner("test.com")
                    planner2.plan()

                    # Second deploy
                    deployer2 = SiteDeployer("test.com", dry_run=False)
                    result2 = deployer2.deploy()
                    assert result2.success

                    # Only analytics and seo stages should have been called again
                    analytics_calls_increased = (
                        mock_stage_apply["analytics"].call_count > first_run_calls["analytics"]
                    )
                    seo_calls_increased = (
                        mock_stage_apply["seo"].call_count > first_run_calls["seo"]
                    )
                    assert analytics_calls_increased, "Analytics stage should have been re-run"
                    assert seo_calls_increased, "SEO stage should have been re-run"

                    # Check unaffected stages kept their original call count
                    for name, mock in mock_stage_apply.items():
                        if name not in ["analytics", "seo"]:
                            assert mock.call_count == first_run_calls[name], (
                                f"Stage {name} should have been skipped, but was called again"
                            )

                    # Also assert skipped behavior via produced report
                    reports_dir = build_dir / "reports"
                    report_path = reports_dir / "apply-report.json"
                    assert report_path.exists()
                    report = json.loads(report_path.read_text())

                    for stage_result in report["stages"]:
                        if stage_result["name"] in ["analytics", "seo"]:
                            assert not stage_result["skipped"], (
                                f"{stage_result['name']} stage should not have been skipped in report"
                            )
                        else:
                            assert stage_result["skipped"], (
                                f"Stage {stage_result['name']} should have been skipped in report"
                            )


def test_atomic_write_survives_failure(
    tmp_path, mock_spec, mock_resolved_spec, mock_wordpress_client
):
    """Test that atomic write survives simulated mid-write failure."""
    build_dir = tmp_path / "build" / "sites" / "test.com"
    build_dir.mkdir(parents=True)

    dummy_spec_path = tmp_path / "site.yaml"

    with patch("fabrik.wordpress.planner.BUILD_ROOT", tmp_path / "build" / "sites"), \
         patch("fabrik.wordpress.planner.resolve_spec_path", return_value=(dummy_spec_path, False)):
        # First run to create initial plan
        planner = Planner("test.com")
        planner.plan()

        plan_path = build_dir / "plan.json"
        original_content = plan_path.read_text()

        # Simulate os.replace failure on first call
        original_replace = __import__("os").replace
        call_count = {"count": 0}

        def failing_replace(src, dst):
            call_count["count"] += 1
            if call_count["count"] == 1:
                # First call fails
                raise OSError("Simulated write failure")
            # Subsequent calls succeed
            return original_replace(src, dst)

        # Trigger rewrite by changing resolved spec hash
        modified_spec = mock_spec.copy()
        modified_spec["site"] = {"domain": "test.com", "name": "New Name"}
        from fabrik.wordpress.resolved_spec import ResolvedSpec

        modified_resolved = ResolvedSpec(site_id="test.com", data=modified_spec)
        mock_resolved_spec.return_value = modified_resolved

        with patch("os.replace", side_effect=failing_replace), \
             patch("fabrik.wordpress.planner.resolve_spec_path", return_value=(dummy_spec_path, False)):
            try:
                planner2 = Planner("test.com")
                planner2.plan()
            except OSError:
                pass  # Expected failure

        assert call_count["count"] > 0, "os.replace was never called"

        # Verify original plan.json is unchanged
        current_content = plan_path.read_text()
        assert current_content == original_content, (
            "Original plan should be unchanged after failure"
        )


def test_force_stage_bypasses_skip(
    tmp_path, mock_spec, mock_stage_apply, mock_resolved_spec, mock_wordpress_client
):
    """Test that --force-stage bypasses skip for named stage."""
    build_dir = tmp_path / "build" / "sites" / "test.com"
    build_dir.mkdir(parents=True)

    dummy_spec_path = tmp_path / "site.yaml"

    with patch("fabrik.wordpress.planner.BUILD_ROOT", tmp_path / "build" / "sites"), \
         patch("fabrik.wordpress.deployer.BUILD_ROOT", tmp_path / "build" / "sites"), \
         patch("fabrik.wordpress.planner.resolve_spec_path", return_value=(dummy_spec_path, False)), \
         patch("fabrik.wordpress.deployer.resolve_spec_path", return_value=(dummy_spec_path, False)), \
         patch("fabrik.wordpress.deployer.load_spec_from_path", return_value=mock_spec):
                # First run
                planner = Planner("test.com")
                planner.plan()

                deployer1 = SiteDeployer("test.com", dry_run=False)
                result1 = deployer1.deploy()
                assert result1.success

                first_run_calls = {name: mock.call_count for name, mock in mock_stage_apply.items()}

                # Second deploy with force_stage=plugins
                deployer2 = SiteDeployer("test.com", dry_run=False, force_stage="plugins")
                result2 = deployer2.deploy()
                assert result2.success

                # Only plugins stage should have been called again
                plugins_calls_increased = (
                    mock_stage_apply["plugins"].call_count > first_run_calls["plugins"]
                )
                assert plugins_calls_increased, "Plugins stage should have been forced to re-run"

                # Other stages should not have been called again
                for name in ["dns", "settings", "theme"]:
                    assert mock_stage_apply[name].call_count == first_run_calls[name], (
                        f"Stage {name} should have been skipped"
                    )
