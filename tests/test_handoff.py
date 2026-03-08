import pytest
from pathlib import Path
import json
import yaml
from fabrik.wordpress.handoff import generate_handoff

def test_generate_handoff_plugin_count(tmp_path):
    site_id = "test-plugins.com"
    build_dir = tmp_path / site_id
    reports_dir = build_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # write apply report
    with open(reports_dir / "apply-report.json", "w") as f:
        json.dump({"stages": [{"name": "plugins", "success": True, "duration_ms": 10}]}, f)

    # write blueprint
    blueprint = {
        "plugins": {
            "base": ["plugin-a", "plugin-b"],
            "add": ["plugin-c", "plugin-b"],
            "skip": ["plugin-a"]
        }
    }
    with open(build_dir / "blueprint.resolved.yaml", "w") as f:
        yaml.dump(blueprint, f)

    handoff_path = generate_handoff(site_id, build_dir)

    with open(handoff_path, "r") as f:
        content = f.read()

    # effective plugins: (base | add) - skip = (plugin-a, plugin-b, plugin-c) - plugin-a = (plugin-b, plugin-c) => 2
    assert "| Plugins | 2 |" in content

def test_generate_handoff_plugin_count_list(tmp_path):
    site_id = "test-plugins-list.com"
    build_dir = tmp_path / site_id
    reports_dir = build_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # write apply report
    with open(reports_dir / "apply-report.json", "w") as f:
        json.dump({"stages": []}, f)

    # write blueprint
    blueprint = {
        "plugins": ["plugin-a", "plugin-b", "plugin-a"]
    }
    with open(build_dir / "blueprint.resolved.yaml", "w") as f:
        yaml.dump(blueprint, f)

    handoff_path = generate_handoff(site_id, build_dir)

    with open(handoff_path, "r") as f:
        content = f.read()

    # effective plugins: 2
    assert "| Plugins | 2 |" in content

