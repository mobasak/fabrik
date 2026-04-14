"""Handoff report generator - creates client-facing documentation."""

import json
from datetime import UTC, datetime
from pathlib import Path


def generate_handoff(site_id: str, build_dir: Path) -> Path:
    """
    Generate handoff.md report from apply and verify reports.

    Args:
        site_id: Site identifier (domain)
        build_dir: Path to build/sites/<site_id>/

    Returns:
        Path to generated handoff.md

    Raises:
        FileNotFoundError: If apply-report.json is missing
    """
    # Read apply report (required)
    apply_report_path = build_dir / "reports" / "apply-report.json"
    if not apply_report_path.exists():
        raise FileNotFoundError(
            f"apply-report.json not found at {apply_report_path}. Run 'fabrik wp apply' first."
        )

    with open(apply_report_path, encoding="utf-8") as f:
        apply_report = json.load(f)

    # Read verify report (optional)
    verify_report_path = build_dir / "reports" / "verify-report.json"
    verify_report = None
    if verify_report_path.exists():
        with open(verify_report_path, encoding="utf-8") as f:
            verify_report = json.load(f)

    # Read blueprint for metadata (optional)
    blueprint_path = build_dir / "blueprint.resolved.yaml"
    blueprint_meta = {}
    if blueprint_path.exists():
        import yaml

        with open(blueprint_path, encoding="utf-8") as f:
            blueprint = yaml.safe_load(f)
            # Extract non-secret metadata only
            if "site" in blueprint:
                blueprint_meta["domain"] = blueprint["site"].get("domain", "")
            if "brand" in blueprint and "name" in blueprint["brand"]:
                blueprint_meta["brand_name"] = blueprint["brand"]["name"]
            if "preset" in blueprint:
                blueprint_meta["preset"] = blueprint["preset"]
            if "plugins" in blueprint:
                plugins = blueprint.get("plugins", {})
                if isinstance(plugins, dict):
                    base = set(plugins.get("base", []))
                    add = set(plugins.get("add", []))
                    skip = set(plugins.get("skip", []))

                    effective_plugins = (base | add) - skip
                    blueprint_meta["plugins_count"] = len(effective_plugins)
                elif isinstance(plugins, list):
                    blueprint_meta["plugins_count"] = len(set(plugins))
                else:
                    blueprint_meta["plugins_count"] = 0

    # Build summary table
    domain = blueprint_meta.get("domain", site_id)
    brand_name = blueprint_meta.get("brand_name", "N/A")
    preset = blueprint_meta.get("preset", "N/A")
    plugins_count = blueprint_meta.get("plugins_count", 0)

    summary_table = f"""| Field | Value |
|-------|-------|
| Domain | {domain} |
| Brand | {brand_name} |
| Preset | {preset} |
| Plugins | {plugins_count} |"""

    # Build stages table
    stages_rows = []
    for stage_result in apply_report.get("stages", []):
        name = stage_result.get("name", "")
        success = stage_result.get("success", False)
        duration = stage_result.get("duration_ms", 0)
        status = "✅" if success else "❌"
        stages_rows.append(f"| {name} | {status} | {duration}ms |")

    stages_table = "| Stage | Status | Duration |\n|-------|--------|----------|\n" + "\n".join(
        stages_rows
    )

    # Build verification section
    if verify_report:
        verify_rows = []
        for check in verify_report.get("checks", []):
            url = check.get("url", "")
            status = check.get("status", "N/A")
            passed = check.get("passed", False)
            passed_icon = "✅" if passed else "❌"
            verify_rows.append(f"| {url} | {status} | {passed_icon} |")

        verify_table = "| URL | Status | Passed |\n|-----|--------|--------|\n" + "\n".join(
            verify_rows
        )
        verify_section = f"""## Verification

{verify_table}"""
    else:
        verify_section = """## Verification

> ⚠️ Verification report not found — run `fabrik wp verify <domain>` first."""

    # Build artifacts list
    artifacts_list = f"""- blueprint: build/sites/{site_id}/blueprint.resolved.yaml
- apply-report: build/sites/{site_id}/reports/apply-report.json
- verify-report: build/sites/{site_id}/reports/verify-report.json"""

    # Render full handoff document
    generated_at = datetime.now(UTC).isoformat()

    handoff_content = f"""# Handoff: {domain}

**Generated:** {generated_at}

## Summary

{summary_table}

## Stages Applied

{stages_table}

{verify_section}

## Artifacts

{artifacts_list}
"""

    # Write handoff.md
    handoff_path = build_dir / "handoff.md"
    with open(handoff_path, "w", encoding="utf-8") as f:
        f.write(handoff_content)

    return handoff_path
