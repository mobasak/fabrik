"""Verification stage - validate deployed site health."""

from datetime import datetime, timezone
import json
from pathlib import Path

import httpx

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.stages import StageResult, time_stage


@time_stage
def apply(
    spec: dict, wp: WordPressClient | None, api: WordPressAPIClient | None, build_dir: Path
) -> StageResult:
    """Verify deployed site by checking URLs."""
    result = StageResult(name="verify", success=True)

    try:
        # Read checks manifest
        checks_path = build_dir / "manifests" / "checks.json"
        if not checks_path.exists():
            result.errors.append("checks.json not found")
            result.success = False
            return result

        with open(checks_path, "r") as f:
            manifest = json.load(f)

        urls = manifest.get("urls", [])
        dry_run = spec.get("dry_run", False)
        domain = spec.get("site", {}).get("domain", "")
        site_id = spec.get("site_name") or domain

        checks = []

        if dry_run:
            # Dry-run: skip HTTP calls, log intent only
            for entry in urls:
                url = entry.get("url", "")
                expected_status = entry.get("expected_status", 200)
                full_url = url if url.startswith("http") else f"https://{domain}{url}"
                checks.append({"url": full_url, "status": expected_status, "passed": True})
        else:
            # Perform actual HTTP checks
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                for entry in urls:
                    url = entry.get("url", "")
                    expected_status = entry.get("expected_status", 200)

                    # Prepend domain if relative
                    full_url = url if url.startswith("http") else f"https://{domain}{url}"

                    try:
                        response = client.get(full_url)
                        status = response.status_code
                        passed = status == expected_status

                        checks.append({"url": full_url, "status": status, "passed": passed})

                        if not passed:
                            result.errors.append(
                                f"{full_url}: expected {expected_status}, got {status}"
                            )

                    except httpx.RequestError as e:
                        checks.append(
                            {"url": full_url, "status": None, "passed": False, "error": str(e)}
                        )
                        result.errors.append(f"{full_url}: {str(e)}")

        # Determine overall result
        overall = "pass" if all(c.get("passed", False) for c in checks) else "fail"
        result.success = overall == "pass"

        # Write verify report
        reports_dir = build_dir / "reports"
        reports_dir.mkdir(exist_ok=True)

        verify_report = {
            "site_id": site_id,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
            "overall": overall,
        }

        verify_report_path = reports_dir / "verify-report.json"
        with open(verify_report_path, "w") as f:
            json.dump(verify_report, f, indent=2)

        result.artifacts_written.append(str(verify_report_path))

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
