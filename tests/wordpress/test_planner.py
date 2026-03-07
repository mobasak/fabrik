"""
Tests for WordPress Planner

Verifies build artifact generation and idempotency.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
import yaml

from fabrik.wordpress.planner import Planner
from fabrik.wordpress.resolved_spec import ResolvedSpec


@pytest.fixture
def mock_resolved_spec():
    """Mock ResolvedSpec for testing."""
    return ResolvedSpec(
        site_id="test.com",
        data={
            "domain": "test.com",
            "title": "Test Site",
            "plugins": {"base": ["contact-form-7"], "add": [], "skip": []},
            "pages": [
                {"slug": "", "title": "Home", "sections": []},
            ],
            "navigation": {"primary": [{"label": "Home", "url": "/"}]},
            "checks": {"urls": ["/"], "require_ssl": True, "require_sitemap": True},
        },
        spec_hash="abc123def456",
    )


@pytest.fixture
def temp_build_root(tmp_path, monkeypatch):
    """Override BUILD_ROOT to use tmp_path."""
    monkeypatch.setattr("fabrik.wordpress.planner.BUILD_ROOT", tmp_path)
    return tmp_path


def test_plan_creates_artifacts(mock_resolved_spec, temp_build_root):
    """Test that plan() creates all required artifacts."""
    with patch(
        "fabrik.wordpress.resolved_spec.ResolvedSpec.from_site", return_value=mock_resolved_spec
    ):
        planner = Planner("test.com")
        build_dir = planner.plan()

        # Verify build directory structure
        assert build_dir.exists()
        assert (build_dir / "manifests").exists()

        # Verify plan.json
        plan_path = build_dir / "plan.json"
        assert plan_path.exists()
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        assert plan["site_id"] == "test.com"
        assert plan["spec_hash"] == "abc123def456"
        assert "created_at" in plan
        assert plan["created_at"].endswith("Z")
        assert "container_name" in plan
        assert "stages" in plan
        assert isinstance(plan["stages"], list)

        # Verify blueprint.resolved.yaml
        blueprint_path = build_dir / "blueprint.resolved.yaml"
        assert blueprint_path.exists()
        blueprint = yaml.safe_load(blueprint_path.read_text(encoding="utf-8"))
        assert blueprint["domain"] == "test.com"
        assert blueprint["title"] == "Test Site"

        # Verify manifests
        assert (build_dir / "manifests" / "plugins.json").exists()
        assert (build_dir / "manifests" / "pages.json").exists()
        assert (build_dir / "manifests" / "menus.json").exists()
        assert (build_dir / "manifests" / "checks.json").exists()


def test_plan_is_idempotent(mock_resolved_spec, temp_build_root):
    """Test that running plan() twice produces identical results."""
    with patch(
        "fabrik.wordpress.resolved_spec.ResolvedSpec.from_site", return_value=mock_resolved_spec
    ):
        planner = Planner("test.com")

        # First run
        build_dir = planner.plan()
        plan1 = json.loads((build_dir / "plan.json").read_text(encoding="utf-8"))

        # Second run
        planner.plan()
        plan2 = json.loads((build_dir / "plan.json").read_text(encoding="utf-8"))

        # Compare full plan (including created_at)
        assert plan1 == plan2


def test_plan_preserves_container_name(mock_resolved_spec, temp_build_root):
    """Test that existing container_name is preserved."""
    with patch(
        "fabrik.wordpress.resolved_spec.ResolvedSpec.from_site", return_value=mock_resolved_spec
    ):
        planner = Planner("test.com")

        # Create existing plan with container_name
        planner.plan_path.parent.mkdir(parents=True, exist_ok=True)
        existing_plan = {
            "site_id": "test.com",
            "spec_hash": "old_hash",
            "created_at": "2024-01-01T00:00:00Z",
            "container_name": "existing-container",
            "stages": [{"name": "deploy", "status": "completed"}],
        }
        planner.plan_path.write_text(json.dumps(existing_plan), encoding="utf-8")

        # Run plan
        planner.plan()

        # Verify container_name and stages are preserved
        plan = json.loads(planner.plan_path.read_text(encoding="utf-8"))
        assert plan["container_name"] == "existing-container"
        assert plan["stages"] == [{"name": "deploy", "status": "completed"}]
        # But spec_hash should be updated
        assert plan["spec_hash"] == "abc123def456"


def test_plan_spec_hash_excludes_secrets(temp_build_root):
    """Test that spec_hash excludes secret keys."""
    # Create two specs differing only in a secret key
    spec1_data = {
        "domain": "test.com",
        "admin_password": "secret123",
        "database_password": "dbpass456",
        "api_token": "token789",
    }
    spec2_data = {
        "domain": "test.com",
        "admin_password": "different_secret",
        "database_password": "different_dbpass",
        "api_token": "different_token",
    }

    spec1 = ResolvedSpec(site_id="test.com", data=spec1_data, spec_hash="")
    spec2 = ResolvedSpec(site_id="test.com", data=spec2_data, spec_hash="")

    # Hashes should be identical (secrets excluded)
    assert spec1.spec_hash == spec2.spec_hash

    # Verify secrets were actually excluded
    sanitized1 = spec1.exclude_secrets()
    assert "admin_password" not in sanitized1
    assert "database_password" not in sanitized1
    assert "api_token" not in sanitized1
    assert "domain" in sanitized1
