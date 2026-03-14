"""Verification stage - validate deployed site health."""

import json
import logging
import socket
import ssl
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.stages import StageResult, time_stage

logger = logging.getLogger(__name__)


def _run_baseline_checks(
    domain: str,
    wp: WordPressClient | None,
    *,
    require_ssl: bool = False,
    require_sitemap: bool = False,
) -> list[dict]:
    """Run 10 baseline health checks against the deployed site.

    Returns a list of dicts with keys: name, passed, detail.
    Fatal failures (ssl_cert, sitemap) also include fatal=True when the
    corresponding require_* flag is True.
    """
    results: list[dict] = []

    # --- Check 1: DNS ---
    try:
        socket.getaddrinfo(domain, None)
        results.append({"name": "dns", "passed": True, "detail": f"DNS resolved for {domain}"})
    except OSError as exc:
        results.append({"name": "dns", "passed": False, "detail": str(exc)})

    # --- Check 2: HTTP → HTTPS redirect ---
    try:
        with httpx.Client(follow_redirects=False, timeout=15) as redirect_client:
            resp = redirect_client.get(f"http://{domain}/")
        location = resp.headers.get("location", "")
        if resp.status_code in (301, 302, 307, 308) and location.startswith("https://"):
            results.append(
                {
                    "name": "http_redirect",
                    "passed": True,
                    "detail": f"Redirects to {location}",
                }
            )
        else:
            results.append(
                {
                    "name": "http_redirect",
                    "passed": False,
                    "detail": (f"status={resp.status_code}, location={location!r}"),
                }
            )
    except httpx.RequestError as exc:
        results.append({"name": "http_redirect", "passed": False, "detail": str(exc)})

    # --- Check 3: SSL certificate (with retry) ---
    max_attempts = 5
    ssl_passed = False
    ssl_detail = ""
    for attempt in range(1, max_attempts + 1):
        try:
            context = ssl.create_default_context()
            sock = socket.create_connection((domain, 443), timeout=10)
            with context.wrap_socket(sock, server_hostname=domain):
                pass
            ssl_passed = True
            ssl_detail = f"SSL certificate valid for {domain}"
            break
        except (ssl.SSLError, OSError, socket.timeout) as exc:
            ssl_detail = str(exc)
            logger.debug("SSL check attempt %d/%d failed: %s", attempt, max_attempts, exc)
            if attempt < max_attempts:
                time.sleep(30)

    if ssl_passed:
        results.append({"name": "ssl_cert", "passed": True, "detail": ssl_detail})
    else:
        results.append(
            {
                "name": "ssl_cert",
                "passed": False,
                "detail": f"SSL check failed after {max_attempts} attempts: {ssl_detail}",
                "fatal": require_ssl,
            }
        )

    # --- Checks 4-8: reuse a single httpx.Client ---
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        # --- Check 4: Homepage 200 ---
        try:
            resp = client.get(f"https://{domain}/")
            passed = resp.status_code == 200
            results.append(
                {
                    "name": "homepage_200",
                    "passed": passed,
                    "detail": f"status={resp.status_code}",
                }
            )
        except httpx.RequestError as exc:
            results.append({"name": "homepage_200", "passed": False, "detail": str(exc)})

        # --- Check 5: WP JSON endpoint 200 ---
        try:
            resp = client.get(f"https://{domain}/wp-json/")
            passed = resp.status_code == 200
            results.append(
                {
                    "name": "wp_json_200",
                    "passed": passed,
                    "detail": f"status={resp.status_code}",
                }
            )
        except httpx.RequestError as exc:
            results.append({"name": "wp_json_200", "passed": False, "detail": str(exc)})

        # --- Check 6: Sitemap (with fallback) ---
        sitemap_urls = ["/wp-sitemap.xml", "/sitemap_index.xml", "/sitemap.xml"]
        sitemap_passed = False
        sitemap_detail = ""
        for path in sitemap_urls:
            try:
                resp = client.get(f"https://{domain}{path}")
                if resp.status_code == 200:
                    sitemap_passed = True
                    sitemap_detail = f"Found sitemap at {path}"
                    break
                else:
                    sitemap_detail = f"{path} returned {resp.status_code}"
            except httpx.RequestError as exc:
                sitemap_detail = str(exc)

        if sitemap_passed:
            results.append({"name": "sitemap", "passed": True, "detail": sitemap_detail})
        else:
            results.append(
                {
                    "name": "sitemap",
                    "passed": False,
                    "detail": f"No sitemap found: {sitemap_detail}",
                    "fatal": require_sitemap,
                }
            )

        # --- Check 7: robots.txt ---
        try:
            resp = client.get(f"https://{domain}/robots.txt")
            passed = resp.status_code == 200 and "User-agent" in resp.text
            results.append(
                {
                    "name": "robots_txt",
                    "passed": passed,
                    "detail": f"status={resp.status_code}, has_user_agent={'User-agent' in resp.text}",
                }
            )
        except httpx.RequestError as exc:
            results.append({"name": "robots_txt", "passed": False, "detail": str(exc)})

        # --- Check 8: wp-login.php 200 ---
        try:
            resp = client.get(f"https://{domain}/wp-login.php")
            passed = resp.status_code == 200
            results.append(
                {
                    "name": "wp_login_200",
                    "passed": passed,
                    "detail": f"status={resp.status_code}",
                }
            )
        except httpx.RequestError as exc:
            results.append({"name": "wp_login_200", "passed": False, "detail": str(exc)})

    # --- Check 9: Required plugins active ---
    if wp is None:
        results.append(
            {
                "name": "required_plugins_active",
                "passed": True,
                "detail": "skipped: wp is None",
            }
        )
    else:
        try:
            raw = wp.plugin_list()
            plugins: list[dict] = raw if isinstance(raw, list) else []
            plugin_statuses = {p["name"]: p["status"] for p in plugins}
            required_plugins = ["akismet/akismet", "hello-dolly/hello"]
            missing_inactive = [
                p
                for p in required_plugins
                if p not in plugin_statuses or plugin_statuses[p] != "active"
            ]
            if missing_inactive:
                results.append(
                    {
                        "name": "required_plugins_active",
                        "passed": False,
                        "detail": f"Missing/inactive: {missing_inactive}",
                    }
                )
            else:
                results.append(
                    {
                        "name": "required_plugins_active",
                        "passed": True,
                        "detail": "All required active",
                    }
                )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "name": "required_plugins_active",
                    "passed": False,
                    "detail": f"plugin_list failed: {exc}",
                }
            )

    return results


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

        with open(checks_path) as f:
            manifest = json.load(f)

        urls = manifest.get("urls", [])
        require_ssl = manifest.get("require_ssl", False)
        require_sitemap = manifest.get("require_sitemap", False)
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

        # Determine overall result from URL checks
        overall = "pass" if all(c.get("passed", False) for c in checks) else "fail"
        result.success = overall == "pass"

        # Run baseline checks (always run in production; skip only in dry-run)
        if not dry_run:
            baseline_checks = _run_baseline_checks(
                domain, wp, require_ssl=require_ssl, require_sitemap=require_sitemap
            )
        else:
            baseline_checks = []

        # Propagate fatal baseline failures to result
        for check in baseline_checks:
            if check.get("fatal", False) and not check.get("passed", True):
                result.success = False
                result.errors.append(
                    f"baseline check '{check['name']}' failed (fatal): {check['detail']}"
                )

        # Write verify report
        reports_dir = build_dir / "reports"
        reports_dir.mkdir(exist_ok=True)

        verify_report = {
            "site_id": site_id,
            "verified_at": datetime.now(UTC).isoformat(),
            "checks": checks,
            "baseline_checks": baseline_checks,
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
