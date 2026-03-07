from click.testing import CliRunner
import pytest
from pathlib import Path
import json
import yaml
from unittest.mock import patch, MagicMock

from fabrik.cli import cli

def test_wp_verify_missing_spec_uses_blueprint(tmp_path):
    runner = CliRunner()
    
    site_id = "test-domain.com"
    build_dir = tmp_path / site_id
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # Create blueprint.resolved.yaml
    blueprint = {
        "site": {
            "domain": "test-domain.com"
        }
    }
    with open(build_dir / "blueprint.resolved.yaml", "w") as f:
        yaml.dump(blueprint, f)
        
    with patch("fabrik.wordpress.planner.BUILD_ROOT", tmp_path), \
         patch("fabrik.cli.load_spec") as mock_load_spec, \
         patch("fabrik.wordpress.stages.verify.apply") as mock_verify_apply, \
         patch("fabrik.cli.generate_handoff", create=True) as mock_generate_handoff_cli, \
         patch("fabrik.wordpress.handoff.generate_handoff") as mock_generate_handoff_module:
         
        mock_load_spec.side_effect = FileNotFoundError("Spec not found")
        
        mock_result = MagicMock()
        mock_result.success = True
        mock_verify_apply.return_value = mock_result
        
        result = runner.invoke(cli, ["wp", "verify", site_id])
        
        assert result.exit_code == 0, result.output
        mock_verify_apply.assert_called_once()
        args, kwargs = mock_verify_apply.call_args
        spec_arg = args[0]
        assert spec_arg["site"]["domain"] == "test-domain.com"

def test_wp_verify_empty_domain(tmp_path):
    runner = CliRunner()
    
    site_id = "empty"
    build_dir = tmp_path / site_id
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # Create blueprint with NO domain
    blueprint = {
        "site": {
            "domain": ""
        }
    }
    with open(build_dir / "blueprint.resolved.yaml", "w") as f:
        yaml.dump(blueprint, f)
        
    with patch("fabrik.wordpress.planner.BUILD_ROOT", tmp_path), \
         patch("fabrik.cli.load_spec", side_effect=FileNotFoundError):
         
        # We pass an empty string to the CLI argument
        result = runner.invoke(cli, ["wp", "verify", ""])
        
        assert result.exit_code == 1
        assert "Domain is empty" in result.output or "Build directory not found" in result.output or "Effective domain is empty" in result.output

