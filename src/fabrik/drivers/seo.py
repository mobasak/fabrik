"""
SEO Client - Wrapper for the SEO keyword research and brief generation service.

This client calls the SEO service API to:
- Register sites for SEO tracking
- Create and run keyword research jobs
- Fetch and manage content briefs (claim → process → submit lifecycle)

Connection: SEO_API_URL env var (default http://localhost:8016)
Auth: SEO_API_KEY env var → Bearer token
"""

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class SEOClient:
    """
    SEO service client for keyword research and content brief management.

    Follows the same pattern as DNSClient: constructor reads URL and token
    from os.getenv(), builds httpx.Client with auth headers, exposes
    _request() helper, and each public method calls _request.

    Usage:
        seo = SEOClient()

        # Register a site
        site = seo.register_site("my-site", "My Site", "example.com", "en-US", "us", "en")

        # Create and run a job
        job = seo.create_job(site["site_id"], ["saas pricing"], page_type_override="pricing")
        seo.run_job(job["id"])

        # Poll until complete
        result = seo.wait_for_job(job["id"])

        # Fetch briefs
        briefs = seo.list_ready_briefs(site["site_id"])
        full_brief = seo.get_brief(briefs[0]["brief_id"])
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize SEO client.

        Args:
            base_url: SEO service URL. Defaults to SEO_API_URL env var
                     or http://localhost:8016
            token: API token for authentication. Defaults to SEO_API_KEY env var.
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv("SEO_API_URL", "http://localhost:8016")
        self.token = token or os.getenv("SEO_API_KEY")
        self.timeout = timeout

        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        else:
            logger.warning(
                "SEO_API_KEY not set — SEO requests will be unauthenticated. "
                "Set SEO_API_KEY in .env for production use."
            )

        self._client = httpx.Client(timeout=timeout, headers=headers)

    def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make HTTP request to SEO service."""
        url = f"{self.base_url}{endpoint}"
        response = self._client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # Site Management
    # =========================================================================

    def get_site_by_domain(self, domain: str) -> dict[str, Any] | None:
        """
        Find a site by domain name.

        Args:
            domain: Domain to look up (case-insensitive match)

        Returns:
            Site dict with site_id, domain, etc. or None if not found
        """
        result = self._request("GET", "/api/v1/sites", params={"active": True})
        for site in result.get("sites", []):
            if site.get("domain", "").lower() == domain.lower():
                return site
        return None

    def register_site(
        self,
        code: str,
        name: str,
        domain: str,
        default_locale: str,
        country_code: str,
        language_code: str,
        rendering_mode: str = "ssr",
        category: str | None = None,
        author_profile_url: str | None = None,
        knowledge_base: dict | None = None,
    ) -> dict[str, Any]:
        """
        Register a new site in the SEO service.

        Args:
            code: Short code (e.g. "my-saas-app")
            name: Display name
            domain: Full domain (e.g. "mysaasapp.com")
            default_locale: Locale string (e.g. "en-US")
            country_code: ISO-2 country (e.g. "us")
            language_code: Language (e.g. "en")
            rendering_mode: "ssr" | "ssg" | "csr" (default "ssr"; SEO service may reject "csr")
            category: Site category (e.g. "saas", "company")
            author_profile_url: URL to author/about page (e.g. "https://mysite.com/about")
            knowledge_base: Optional JSONB config (may include indexnow_api_key, search_console_property)

        Returns:
            Created site dict with site_id
        """
        payload: dict[str, Any] = {
            "code": code,
            "name": name,
            "domain": domain,
            "default_locale": default_locale,
            "country_code": country_code,
            "language_code": language_code,
            "rendering_mode": rendering_mode,
        }
        if category is not None:
            payload["category"] = category
        if author_profile_url is not None:
            payload["author_profile_url"] = author_profile_url
        if knowledge_base is not None:
            payload["knowledge_base"] = knowledge_base
        return self._request("POST", "/api/v1/sites", json=payload)

    def ensure_site(
        self,
        domain: str,
        name: str,
        country_code: str = "us",
        language_code: str = "en",
        category: str | None = None,
    ) -> str:
        """
        Return site_id for domain, creating the site if it doesn't exist.

        Args:
            domain: Domain name
            name: Display name (used only if creating)
            country_code: ISO-2 country code
            language_code: Language code
            category: Site category

        Returns:
            site_id as string
        """
        existing = self.get_site_by_domain(domain)
        if existing:
            return str(existing["site_id"])

        code = domain.replace(".", "-")
        locale = f"{language_code}-{country_code.upper()}"
        site = self.register_site(
            code=code,
            name=name,
            domain=domain,
            default_locale=locale,
            country_code=country_code,
            language_code=language_code,
            category=category,
        )
        logger.info("Registered new site in SEO service: %s → %s", domain, site["site_id"])
        return str(site["site_id"])

    # =========================================================================
    # Job Management
    # =========================================================================

    def create_job(
        self,
        site_id: str,
        seed_topics: list[str],
        country_code: str | None = None,
        language_code: str | None = None,
        page_type_override: str | None = None,
        provider_config: dict | None = None,
    ) -> dict[str, Any]:
        """
        Create a new SEO keyword research job.

        Args:
            site_id: UUID of the site
            seed_topics: Topic strings (usually 1 per job)
            country_code: Target market ISO-2 code
            language_code: Content language
            page_type_override: Force page type for all briefs in this job
            provider_config: Override DataForSEO/Scrapingdog settings

        Returns:
            Job dict with id, status, etc.
        """
        payload: dict[str, Any] = {"seed_topics": seed_topics}
        if country_code is not None:
            payload["country_code"] = country_code
        if language_code is not None:
            payload["language_code"] = language_code
        if page_type_override is not None:
            payload["page_type_override"] = page_type_override
        if provider_config is not None:
            payload["provider_config"] = provider_config
        return self._request("POST", f"/api/v1/sites/{site_id}/seo/jobs", json=payload)

    def run_job(self, job_id: str) -> dict[str, Any]:
        """
        Kick off the 11-stage SEO pipeline for a job.

        Returns 202 response with job id and status.
        """
        return self._request("POST", f"/api/v1/seo/jobs/{job_id}/run")

    def get_job(self, job_id: str) -> dict[str, Any]:
        """
        Get current job status.

        Status values: created → running → completed | failed
        """
        return self._request("GET", f"/api/v1/seo/jobs/{job_id}")

    def wait_for_job(
        self, job_id: str, timeout: int = 300, poll_interval: int = 5
    ) -> dict[str, Any]:
        """
        Poll a job until it completes or fails.

        Args:
            job_id: Job UUID
            timeout: Max seconds to wait
            poll_interval: Seconds between polls

        Returns:
            Final job dict with status "completed" or "failed"

        Raises:
            TimeoutError: If job doesn't finish within timeout
            RuntimeError: If job fails
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = self.get_job(job_id)
            if job["status"] == "completed":
                return job
            if job["status"] == "failed":
                raise RuntimeError(f"SEO job {job_id} failed: {job.get('error_message')}")
            time.sleep(poll_interval)
        raise TimeoutError(f"SEO job {job_id} did not complete within {timeout}s")

    # =========================================================================
    # Brief Management
    # =========================================================================

    def list_ready_briefs(self, site_id: str) -> list[dict[str, Any]]:
        """
        List briefs with status=ready for a site.

        Returns:
            List of brief summary dicts
        """
        result = self._request(
            "GET", "/api/v1/briefs", params={"status": "ready", "site_id": site_id}
        )
        return result.get("briefs", [])

    def list_briefs(self, site_id: str, status: str | None = None) -> list[dict[str, Any]]:
        """
        List briefs for a site, optionally filtered by status.

        Args:
            site_id: Site UUID
            status: Filter by status (ready, draft, claimed, submitted, accepted)

        Returns:
            List of brief summary dicts
        """
        params: dict[str, Any] = {"site_id": site_id}
        if status is not None:
            params["status"] = status
        result = self._request("GET", "/api/v1/briefs", params=params)
        return result.get("briefs", [])

    def get_brief(self, brief_id: str) -> dict[str, Any]:
        """
        Get full brief payload including page_record, geo, content_contract,
        and cannibalization_guard.

        Returns:
            Full brief dict
        """
        return self._request("GET", f"/api/v1/briefs/{brief_id}")

    def claim_brief(self, brief_id: str, worker_id: str) -> dict[str, Any]:
        """
        Claim a ready brief for processing.

        Args:
            brief_id: Brief UUID
            worker_id: Identifier for the claiming worker

        Returns:
            Claimed brief dict with lock details

        Raises:
            httpx.HTTPStatusError: 409 if brief is not claimable
        """
        return self._request(
            "POST", f"/api/v1/briefs/{brief_id}/claim", json={"worker_id": worker_id}
        )

    def release_brief(self, brief_id: str, worker_id: str) -> dict[str, Any]:
        """
        Release a claimed brief back to ready state.

        Args:
            brief_id: Brief UUID
            worker_id: Must match the claiming worker

        Returns:
            Response dict with brief_id and status
        """
        return self._request(
            "POST", f"/api/v1/briefs/{brief_id}/release", json={"worker_id": worker_id}
        )

    def submit_brief(self, brief_id: str, worker_id: str, submission: dict) -> dict[str, Any]:
        """
        Submit completed work for a claimed brief.

        Args:
            brief_id: Brief UUID
            worker_id: Must match the claiming worker
            submission: SubmissionPayload dict with fields:
                - final_url, final_slug, final_title, final_h1
                - final_page_type, schema_primary_used
                - schema_secondary_used (list), status

        Returns:
            Response dict with brief_id and status
        """
        return self._request(
            "POST",
            f"/api/v1/briefs/{brief_id}/submit",
            json={"worker_id": worker_id, "submission": submission},
        )

    # =========================================================================
    # Context Manager
    # =========================================================================

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._client.close()

    def close(self):
        """Close HTTP client."""
        self._client.close()
