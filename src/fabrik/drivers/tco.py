"""
TCO Client - Wrapper for the Triggered Content Orchestration service.

This client calls the TCO service API to generate full page packages
from SEO content briefs. TCO runs a multi-step pipeline:
  brief validation → evidence extraction → section planning →
  content generation → metadata → JSON-LD → output validation

Connection: TCO_API_URL env var (default http://localhost:8025)
Auth: TCO_API_KEY env var → Bearer token
"""

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class TCOClient:
    """
    Triggered Content Orchestration client for AI content generation.

    Usage:
        tco = TCOClient()
        page_package = tco.generate_from_brief(brief_dict)
        # page_package contains: page_payload, rendered_sections, json_ld,
        # validation, evidence_manifest, generation_metrics
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 300.0,
    ):
        """
        Initialize TCO client.

        Args:
            base_url: TCO service URL. Defaults to TCO_API_URL env var
                     or http://localhost:8025
            token: API token for authentication. Defaults to TCO_API_KEY env var.
            timeout: Request timeout in seconds. Default 300s because TCO
                    runs a full LLM pipeline that can take minutes.
        """
        self.base_url = base_url or os.getenv("TCO_API_URL", "http://localhost:8025")
        self.token = token or os.getenv("TCO_API_KEY")
        self.timeout = timeout

        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self._client = httpx.Client(timeout=timeout, headers=headers)

    def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make HTTP request to TCO service."""
        url = f"{self.base_url}{endpoint}"
        response = self._client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # Content Generation
    # =========================================================================

    def generate_from_brief(self, brief: dict[str, Any]) -> dict[str, Any]:
        """
        Generate a full page package from a content brief.

        The brief dict must contain exactly the fields expected by TCO's
        ContentBrief schema (extra="forbid"):
            brief_version, brief_id, site_id, job_id, cluster_id,
            page_record, geo, content_contract, cannibalization_guard, status

        Args:
            brief: ContentBrief-compatible dict

        Returns:
            PagePackageResponse dict containing:
            - brief_id: str
            - page_payload: dict (page_type, slug, seo_title, meta_description, etc.)
            - rendered_sections: list[dict] (type + content per section)
            - json_ld: list[dict] (structured data blocks)
            - validation: dict (is_valid, errors, warnings)
            - evidence_manifest: dict (grounded, partial, omitted)
            - generation_metrics: dict (steps, total_latency_ms)

        Raises:
            httpx.HTTPStatusError: 422 if brief validation fails,
                                   502 if Kilo CLI invocation fails
        """
        return self._request("POST", "/ai-content/generate-from-brief", json=brief)

    def health(self) -> dict[str, Any]:
        """Check TCO service health."""
        return self._request("GET", "/ai-content/health")

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
