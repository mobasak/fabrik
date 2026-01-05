"""
WordPress REST API Client - HTTP client for WordPress REST API operations.

Provides programmatic access to WordPress content: posts, pages, media, users, etc.
"""

import base64
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class WPCredentials:
    """WordPress API credentials."""

    url: str  # Site URL (e.g., https://wp-test.vps1.ocoron.com)
    username: str
    password: str  # Application password or regular password

    @property
    def base_url(self) -> str:
        """Get REST API base URL."""
        return f"{self.url.rstrip('/')}/wp-json/wp/v2"

    @property
    def auth_header(self) -> str:
        """Get Basic Auth header value."""
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"


@dataclass
class WPPost:
    """WordPress post/page data."""

    id: int | None = None
    title: str = ""
    content: str = ""
    excerpt: str = ""
    slug: str = ""
    status: str = "draft"  # draft, publish, pending, private
    type: str = "post"  # post, page
    categories: list[int] = field(default_factory=list)
    tags: list[int] = field(default_factory=list)
    featured_media: int = 0
    meta: dict = field(default_factory=dict)


class WordPressAPIClient:
    """
    WordPress REST API client for content operations.

    Requires Application Password or regular auth.
    """

    def __init__(self, credentials: WPCredentials, timeout: int = 30):
        """
        Initialize WordPress API client.

        Args:
            credentials: WordPress credentials
            timeout: Request timeout in seconds
        """
        self.credentials = credentials
        self.timeout = timeout
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.credentials.base_url,
                headers={
                    "Authorization": self.credentials.auth_header,
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json: dict | None = None,
    ) -> Any:
        """Make API request."""
        response = self.client.request(
            method=method,
            url=endpoint,
            params=params,
            json=json,
        )
        response.raise_for_status()
        return response.json() if response.content else None

    # ========== Posts ==========

    def list_posts(
        self,
        per_page: int = 10,
        page: int = 1,
        status: str = "any",
        search: str | None = None,
    ) -> list[dict]:
        """List posts."""
        params = {
            "per_page": per_page,
            "page": page,
            "status": status,
        }
        if search:
            params["search"] = search
        return self._request("GET", "/posts", params=params)

    def get_post(self, post_id: int) -> dict:
        """Get a single post."""
        return self._request("GET", f"/posts/{post_id}")

    def create_post(self, post: WPPost) -> dict:
        """Create a new post."""
        data = {
            "title": post.title,
            "content": post.content,
            "excerpt": post.excerpt,
            "slug": post.slug,
            "status": post.status,
            "categories": post.categories,
            "tags": post.tags,
            "featured_media": post.featured_media,
            "meta": post.meta,
        }
        # Remove empty values
        data = {k: v for k, v in data.items() if v}
        return self._request("POST", "/posts", json=data)

    def update_post(self, post_id: int, **fields) -> dict:
        """Update a post."""
        return self._request("POST", f"/posts/{post_id}", json=fields)

    def delete_post(self, post_id: int, force: bool = False) -> dict:
        """Delete a post."""
        return self._request("DELETE", f"/posts/{post_id}", params={"force": force})

    # ========== Pages ==========

    def list_pages(
        self,
        per_page: int = 10,
        page: int = 1,
        status: str = "any",
    ) -> list[dict]:
        """List pages."""
        return self._request(
            "GET",
            "/pages",
            params={
                "per_page": per_page,
                "page": page,
                "status": status,
            },
        )

    def get_page(self, page_id: int) -> dict:
        """Get a single page."""
        return self._request("GET", f"/pages/{page_id}")

    def create_page(self, post: WPPost) -> dict:
        """Create a new page."""
        data = {
            "title": post.title,
            "content": post.content,
            "excerpt": post.excerpt,
            "slug": post.slug,
            "status": post.status,
            "featured_media": post.featured_media,
            "meta": post.meta,
        }
        data = {k: v for k, v in data.items() if v}
        return self._request("POST", "/pages", json=data)

    def update_page(self, page_id: int, **fields) -> dict:
        """Update a page."""
        return self._request("POST", f"/pages/{page_id}", json=fields)

    def delete_page(self, page_id: int, force: bool = False) -> dict:
        """Delete a page."""
        return self._request("DELETE", f"/pages/{page_id}", params={"force": force})

    # ========== Media ==========

    def list_media(self, per_page: int = 10, page: int = 1) -> list[dict]:
        """List media items."""
        return self._request(
            "GET",
            "/media",
            params={
                "per_page": per_page,
                "page": page,
            },
        )

    def get_media(self, media_id: int) -> dict:
        """Get a single media item."""
        return self._request("GET", f"/media/{media_id}")

    def upload_media(
        self,
        file_path: str,
        title: str | None = None,
        alt_text: str | None = None,
    ) -> dict:
        """
        Upload a media file.

        Args:
            file_path: Path to the file to upload
            title: Optional title for the media
            alt_text: Optional alt text for images
        """
        import mimetypes
        from pathlib import Path

        path = Path(file_path)
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"

        # Need to use different client for file upload
        with open(file_path, "rb") as f:
            response = httpx.post(
                f"{self.credentials.base_url}/media",
                headers={
                    "Authorization": self.credentials.auth_header,
                    "Content-Disposition": f'attachment; filename="{path.name}"',
                    "Content-Type": content_type,
                },
                content=f.read(),
                timeout=60,
            )
        response.raise_for_status()
        media = response.json()

        # Update title/alt if provided
        updates = {}
        if title:
            updates["title"] = title
        if alt_text:
            updates["alt_text"] = alt_text
        if updates:
            media = self.update_media(media["id"], **updates)

        return media

    def update_media(self, media_id: int, **fields) -> dict:
        """Update media metadata."""
        return self._request("POST", f"/media/{media_id}", json=fields)

    def delete_media(self, media_id: int, force: bool = True) -> dict:
        """Delete a media item."""
        return self._request("DELETE", f"/media/{media_id}", params={"force": force})

    # ========== Categories ==========

    def list_categories(self, per_page: int = 100) -> list[dict]:
        """List categories."""
        return self._request("GET", "/categories", params={"per_page": per_page})

    def create_category(self, name: str, slug: str | None = None, parent: int = 0) -> dict:
        """Create a category."""
        data = {"name": name, "parent": parent}
        if slug:
            data["slug"] = slug
        return self._request("POST", "/categories", json=data)

    def delete_category(self, category_id: int, force: bool = True) -> dict:
        """Delete a category."""
        return self._request("DELETE", f"/categories/{category_id}", params={"force": force})

    # ========== Tags ==========

    def list_tags(self, per_page: int = 100) -> list[dict]:
        """List tags."""
        return self._request("GET", "/tags", params={"per_page": per_page})

    def create_tag(self, name: str, slug: str | None = None) -> dict:
        """Create a tag."""
        data = {"name": name}
        if slug:
            data["slug"] = slug
        return self._request("POST", "/tags", json=data)

    def delete_tag(self, tag_id: int, force: bool = True) -> dict:
        """Delete a tag."""
        return self._request("DELETE", f"/tags/{tag_id}", params={"force": force})

    # ========== Users ==========

    def list_users(self, per_page: int = 10) -> list[dict]:
        """List users."""
        return self._request("GET", "/users", params={"per_page": per_page})

    def get_user(self, user_id: int) -> dict:
        """Get a user."""
        return self._request("GET", f"/users/{user_id}")

    def get_me(self) -> dict:
        """Get current authenticated user."""
        return self._request("GET", "/users/me")

    # ========== Settings ==========

    def get_settings(self) -> dict:
        """Get site settings."""
        return self._request("GET", "/settings")

    def update_settings(self, **settings) -> dict:
        """Update site settings."""
        return self._request("POST", "/settings", json=settings)

    # ========== Utility ==========

    def health_check(self) -> bool:
        """Check if API is accessible."""
        try:
            self.get_me()
            return True
        except Exception:
            return False

    def close(self):
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def get_wordpress_api(
    url: str,
    username: str,
    password: str,
) -> WordPressAPIClient:
    """
    Get WordPress API client.

    Args:
        url: WordPress site URL
        username: Admin username
        password: Application password or regular password

    Returns:
        Configured WordPressAPIClient
    """
    credentials = WPCredentials(url=url, username=username, password=password)
    return WordPressAPIClient(credentials)
