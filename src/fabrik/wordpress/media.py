"""
WordPress Media Uploader - Upload brand assets to WordPress.

Handles:
- Logo upload and site identity
- Favicon/site icon
- General media uploads via REST API
"""

import os
from dataclasses import dataclass
from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient, get_wordpress_client
from fabrik.drivers.wordpress_api import WordPressAPIClient, WPCredentials


@dataclass
class UploadedMedia:
    """Uploaded media item details."""

    id: int
    url: str
    title: str
    filename: str


class MediaUploader:
    """
    Upload and manage WordPress media assets.

    Usage:
        uploader = MediaUploader("wp-test", api_url, api_user, api_pass)
        logo = uploader.upload_file("/path/to/logo.svg", title="Site Logo")
        uploader.set_site_icon(logo.id)
    """

    def __init__(
        self,
        site_name: str,
        api_url: str | None = None,
        api_user: str | None = None,
        api_password: str | None = None,
        wp_client: WordPressClient | None = None,
        api_client: WordPressAPIClient | None = None,
    ):
        """
        Initialize media uploader.

        Args:
            site_name: WordPress site name
            api_url: WordPress site URL for REST API
            api_user: Admin username
            api_password: Application password
            wp_client: Optional WP-CLI client
            api_client: Optional REST API client
        """
        self.site_name = site_name
        self.wp = wp_client or get_wordpress_client(site_name)

        if api_client:
            self.api = api_client
        elif api_url and api_user and api_password:
            creds = WPCredentials(url=api_url, username=api_user, password=api_password)
            self.api = WordPressAPIClient(creds)
        else:
            self.api = None

    def upload_file(
        self,
        file_path: str,
        title: str | None = None,
        alt_text: str | None = None,
    ) -> UploadedMedia:
        """
        Upload a file to WordPress media library.

        Args:
            file_path: Path to the file to upload
            title: Optional title for the media
            alt_text: Optional alt text for images

        Returns:
            UploadedMedia with details

        Raises:
            ValueError: If no API client configured
            FileNotFoundError: If file doesn't exist
        """
        if not self.api:
            raise ValueError("REST API client required for media uploads")

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        result = self.api.upload_media(
            file_path=str(path),
            title=title or path.stem,
            alt_text=alt_text,
        )

        return UploadedMedia(
            id=result["id"],
            url=result.get("source_url", result.get("guid", {}).get("rendered", "")),
            title=result.get("title", {}).get("rendered", path.stem),
            filename=path.name,
        )

    def set_site_icon(self, media_id: int) -> bool:
        """
        Set the site icon (favicon) from an uploaded media item.

        Args:
            media_id: ID of the uploaded media

        Returns:
            True if successful
        """
        self.wp.option_update("site_icon", str(media_id))
        return True

    def set_site_logo(self, media_id: int) -> bool:
        """
        Set the site logo (for themes that support it).

        Args:
            media_id: ID of the uploaded media

        Returns:
            True if successful
        """
        # Most themes use custom_logo theme mod
        self.wp.run(f"theme mod set custom_logo '{media_id}'")
        return True

    def upload_brand_assets(self, brand: dict, assets_dir: str) -> dict:
        """
        Upload all brand assets from spec.

        Args:
            brand: Brand section from site spec with 'logo' subsection
            assets_dir: Base directory for asset files

        Returns:
            Dict mapping asset type to UploadedMedia
        """
        uploaded = {}
        logo_config = brand.get("logo", {})

        for asset_type, relative_path in logo_config.items():
            if not relative_path:
                continue

            full_path = os.path.join(assets_dir, relative_path)
            if not os.path.exists(full_path):
                print(f"Warning: Asset not found: {full_path}")
                continue

            try:
                media = self.upload_file(
                    full_path,
                    title=f"Brand {asset_type.replace('_', ' ').title()}",
                    alt_text=f"{brand.get('name', 'Site')} {asset_type}",
                )
                uploaded[asset_type] = media

                # Auto-assign based on type
                if asset_type == "favicon":
                    self.set_site_icon(media.id)
                elif asset_type == "primary":
                    self.set_site_logo(media.id)

            except Exception as e:
                print(f"Warning: Failed to upload {asset_type}: {e}")

        return uploaded

    def list_media(self, per_page: int = 20) -> list[dict]:
        """List media items."""
        if not self.api:
            raise ValueError("REST API client required")
        return self.api.list_media(per_page=per_page)

    def delete_media(self, media_id: int) -> bool:
        """Delete a media item."""
        if not self.api:
            raise ValueError("REST API client required")
        self.api.delete_media(media_id)
        return True


def upload_brand_assets(
    site_name: str,
    brand: dict,
    assets_dir: str,
    api_url: str,
    api_user: str,
    api_password: str,
) -> dict:
    """
    Convenience function to upload brand assets.

    Args:
        site_name: WordPress site name
        brand: Brand section from site spec
        assets_dir: Directory containing asset files
        api_url: WordPress site URL
        api_user: Admin username
        api_password: Application password

    Returns:
        Dict mapping asset type to UploadedMedia
    """
    uploader = MediaUploader(
        site_name=site_name,
        api_url=api_url,
        api_user=api_user,
        api_password=api_password,
    )
    return uploader.upload_brand_assets(brand, assets_dir)
