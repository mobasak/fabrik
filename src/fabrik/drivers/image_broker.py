"""
Image Broker Client - Wrapper for the unified stock image API.

This client calls the Image Broker service to search, select, and download
stock images from Pexels/Pixabay with smart routing, scoring, and caching.

Connection: IMAGE_BROKER_URL env var (default http://localhost:18016)
Auth: None required (internal service)
"""

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ImageBrokerClient:
    """
    Image Broker client for stock image selection and download.

    Usage:
        ib = ImageBrokerClient()

        # Auto-select and download a hero image
        result = ib.auto_download("saas pricing dashboard")
        if result:
            local_url = result["selected"][0]["local_url"]

        # Search without downloading
        results = ib.search("modern office workspace", orientation="landscape")
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 60.0,
    ):
        """
        Initialize Image Broker client.

        Args:
            base_url: Image Broker service URL. Defaults to IMAGE_BROKER_URL
                     env var or http://localhost:18016
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv("IMAGE_BROKER_URL", "http://localhost:18016")
        self.timeout = timeout

        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        self._client = httpx.Client(timeout=timeout, headers=headers)

    def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make HTTP request to Image Broker service."""
        url = f"{self.base_url}{endpoint}"
        response = self._client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # Image Operations
    # =========================================================================

    def auto_download(
        self,
        query: str,
        intent: str = "hero",
        count: int = 1,
        image_type: str = "photo",
        orientation: str | None = None,
        topic: str | None = None,
        need_faces: bool = False,
    ) -> dict[str, Any] | None:
        """
        Auto-select and download images with smart provider routing.

        Args:
            query: Search query (e.g. primary keyword)
            intent: Image intent — "hero", "inline", "thumbnail", "social"
            count: Number of images to select (1-10)
            image_type: "photo", "illustration", "vector"
            orientation: "landscape", "portrait", "square" or None
            topic: Routing hint — "people", "product", "abstract", "office", etc.
            need_faces: If True, prefer Pexels for better people photos

        Returns:
            AutoDownloadResponse dict with:
            - success: bool
            - selected: list of SelectedImage dicts (provider, score, local_url, etc.)
            - query_used, provider_used, routing_reason
            Returns None if the request fails or success is False.
        """
        payload: dict[str, Any] = {
            "query": query,
            "intent": intent,
            "count": count,
            "image_type": image_type,
            "need_faces": need_faces,
        }
        if orientation is not None:
            payload["orientation"] = orientation
        if topic is not None:
            payload["topic"] = topic

        try:
            result = self._request("POST", "/api/v1/auto-download", json=payload)
            if not result.get("success", False):
                logger.warning("Image Broker returned success=false for query=%r", query)
                return None
            return result
        except httpx.HTTPError as exc:
            logger.warning("Image Broker request failed for query=%r: %s", query, exc)
            return None

    def search(
        self,
        query: str,
        orientation: str | None = None,
        per_page: int = 10,
    ) -> dict[str, Any]:
        """
        Search for images without downloading.

        Args:
            query: Search query
            orientation: "landscape", "portrait", "square" or None
            per_page: Results per page

        Returns:
            SearchResponse dict with results from all providers
        """
        params: dict[str, Any] = {"query": query, "per_page": per_page}
        if orientation is not None:
            params["orientation"] = orientation
        return self._request("GET", "/api/v1/search", params=params)

    def download_image(self, image_url: str, dest_path: str) -> str:
        """
        Download an image from a URL to a local file.

        Useful for downloading images from Image Broker's cache URL
        before uploading to WordPress.

        Args:
            image_url: Full URL to the image (e.g. Image Broker cache URL)
            dest_path: Local filesystem path to save the image

        Returns:
            The dest_path on success
        """
        response = self._client.get(image_url)
        response.raise_for_status()
        from pathlib import Path

        Path(dest_path).write_bytes(response.content)
        return dest_path

    def health(self) -> dict[str, Any]:
        """Check Image Broker service health."""
        return self._request("GET", "/api/v1/health")

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
