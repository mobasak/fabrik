#!/usr/bin/env python3
"""
Container Image Discovery Tool for Fabrik

Search, evaluate, and select container images from multiple registries:
- Docker Hub (docker.io)
- LinuxServer.io (lscr.io)
- GitHub Container Registry (ghcr.io)
- TrueForge/ContainerForge (oci.trueforge.org)

Focuses on arm64-compatible, minimal, secure images for VPS deployment.

Usage:
    python container_images.py search nginx
    python container_images.py check-arch redis:7-alpine
    python container_images.py trueforge list
    python container_images.py trueforge tags home-assistant
"""

import argparse
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

# Load environment
load_dotenv(Path(__file__).parent.parent / ".env")

console = Console()

# Credentials
DOCKER_HUB_USERNAME = os.getenv("DOCKER_HUB_USERNAME")
DOCKER_HUB_ACCESS_TOKEN = os.getenv("DOCKER_HUB_ACCESS_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # Optional, for higher rate limits

# API endpoints
DOCKER_HUB_API = "https://hub.docker.com/v2"
DOCKER_REGISTRY_API = "https://registry-1.docker.io/v2"
GITHUB_API = "https://api.github.com"
TRUEFORGE_REGISTRY = "https://oci.trueforge.org/v2"
TRUEFORGE_ORG = "trueforge-org"


class DockerHubClient:
    """Client for Docker Hub API operations."""

    def __init__(self):
        self.username = DOCKER_HUB_USERNAME
        self.token = DOCKER_HUB_ACCESS_TOKEN
        self.client = httpx.Client(timeout=30)

    def _get_auth_header(self) -> dict:
        """Get authentication header for Docker Hub API."""
        if self.username and self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    def _get_registry_token(self, repository: str) -> str:
        """Get JWT token for registry API access."""
        scope = f"repository:{repository}:pull"
        url = f"https://auth.docker.io/token?service=registry.docker.io&scope={scope}"

        auth = None
        if self.username and self.token:
            auth = (self.username, self.token)

        resp = self.client.get(url, auth=auth)
        resp.raise_for_status()
        return resp.json()["token"]

    def search(self, query: str, limit: int = 25) -> list[dict]:
        """Search for images on Docker Hub."""
        url = f"{DOCKER_HUB_API}/search/repositories"
        params = {"query": query, "page_size": limit}

        resp = self.client.get(url, params=params, headers=self._get_auth_header())
        resp.raise_for_status()
        return resp.json().get("results", [])

    def get_repository(self, namespace: str, repository: str) -> dict:
        """Get repository details."""
        url = f"{DOCKER_HUB_API}/repositories/{namespace}/{repository}"
        resp = self.client.get(url, headers=self._get_auth_header())
        resp.raise_for_status()
        return resp.json()

    def get_tags(self, namespace: str, repository: str, limit: int = 25) -> list[dict]:
        """Get tags for a repository."""
        url = f"{DOCKER_HUB_API}/repositories/{namespace}/{repository}/tags"
        params = {"page_size": limit, "ordering": "-last_updated"}

        resp = self.client.get(url, params=params, headers=self._get_auth_header())
        resp.raise_for_status()
        return resp.json().get("results", [])

    def get_manifest(self, repository: str, tag: str = "latest") -> dict:
        """Get image manifest to check architecture support."""
        if "/" not in repository:
            repository = f"library/{repository}"

        token = self._get_registry_token(repository)

        url = f"{DOCKER_REGISTRY_API}/{repository}/manifests/{tag}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.oci.image.index.v1+json",
        }

        resp = self.client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()


class TrueForgeClient:
    """Client for TrueForge/ContainerForge registry via GitHub API."""

    def __init__(self):
        self.token = GITHUB_TOKEN
        self.client = httpx.Client(timeout=30)
        self.org = TRUEFORGE_ORG

    def _get_headers(self) -> dict:
        """Get headers for GitHub API."""
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def list_packages(self, limit: int = 100) -> list[dict]:
        """List all container packages in TrueForge org."""
        url = f"{GITHUB_API}/orgs/{self.org}/packages"
        params = {"package_type": "container", "per_page": limit}

        try:
            resp = self.client.get(url, params=params, headers=self._get_headers())
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                console.print(
                    "[yellow]Note: Set GITHUB_TOKEN in .env for better rate limits[/yellow]"
                )
            raise

    def get_package_versions(self, package_name: str, limit: int = 20) -> list[dict]:
        """Get versions/tags for a specific package."""
        url = f"{GITHUB_API}/orgs/{self.org}/packages/container/{package_name}/versions"
        params = {"per_page": limit}

        resp = self.client.get(url, params=params, headers=self._get_headers())
        resp.raise_for_status()
        return resp.json()

    def get_package_info(self, package_name: str) -> dict:
        """Get package metadata."""
        url = f"{GITHUB_API}/orgs/{self.org}/packages/container/{package_name}"

        resp = self.client.get(url, headers=self._get_headers())
        resp.raise_for_status()
        return resp.json()

    def check_arm64_via_oci(self, image_name: str, tag: str = "latest") -> dict:
        """Check arm64 support via OCI registry API."""
        # TrueForge images are at oci.trueforge.org/tccr/<name>
        url = f"{TRUEFORGE_REGISTRY}/tccr/{image_name}/manifests/{tag}"
        headers = {
            "Accept": "application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.oci.image.index.v1+json"
        }

        try:
            resp = self.client.get(url, headers=headers)
            resp.raise_for_status()
            manifest = resp.json()

            architectures = []
            if manifest.get("mediaType") in [
                "application/vnd.docker.distribution.manifest.list.v2+json",
                "application/vnd.oci.image.index.v1+json",
            ]:
                for m in manifest.get("manifests", []):
                    platform = m.get("platform", {})
                    arch = platform.get("architecture", "unknown")
                    os_name = platform.get("os", "unknown")
                    architectures.append(f"{os_name}/{arch}")

            arm64_supported = any("arm64" in a or "aarch64" in a for a in architectures)

            return {
                "image": f"oci.trueforge.org/tccr/{image_name}:{tag}",
                "arm64_supported": arm64_supported,
                "architectures": architectures,
                "multi_arch": len(architectures) > 1,
            }
        except Exception as e:
            return {
                "image": f"oci.trueforge.org/tccr/{image_name}:{tag}",
                "arm64_supported": None,
                "error": str(e),
                "architectures": [],
            }


def check_arm64_support(image: str, tag: str = "latest") -> dict:
    """Check if image supports arm64 architecture."""
    # Parse image name
    if ":" in image:
        image, tag = image.rsplit(":", 1)

    # Handle different registries
    if image.startswith("oci.trueforge.org/"):
        # TrueForge image
        image_name = image.replace("oci.trueforge.org/tccr/", "")
        client = TrueForgeClient()
        return client.check_arm64_via_oci(image_name, tag)
    elif image.startswith("lscr.io/") or image.startswith("ghcr.io/"):
        return _check_arm64_via_docker(image, tag)
    else:
        # Docker Hub image
        client = DockerHubClient()
        repository = image
        if "/" not in repository:
            repository = f"library/{repository}"

        try:
            manifest = client.get_manifest(repository, tag)

            architectures = []
            if manifest.get("mediaType") in [
                "application/vnd.docker.distribution.manifest.list.v2+json",
                "application/vnd.oci.image.index.v1+json",
            ]:
                for m in manifest.get("manifests", []):
                    platform = m.get("platform", {})
                    arch = platform.get("architecture", "unknown")
                    os_name = platform.get("os", "unknown")
                    variant = platform.get("variant", "")
                    arch_str = f"{os_name}/{arch}"
                    if variant:
                        arch_str += f"/{variant}"
                    architectures.append(arch_str)

            arm64_supported = any("arm64" in a or "aarch64" in a for a in architectures)

            return {
                "image": f"{image}:{tag}",
                "arm64_supported": arm64_supported,
                "architectures": architectures,
                "multi_arch": len(architectures) > 1,
            }
        except (ValueError, KeyError, TypeError, httpx.HTTPError) as e:
            return {
                "image": f"{image}:{tag}",
                "arm64_supported": None,
                "error": str(e),
                "architectures": [],
            }
        except Exception as e:
            return {
                "image": f"{image}:{tag}",
                "arm64_supported": None,
                "error": f"Unexpected error: {str(e)}",
                "architectures": [],
            }


def _check_arm64_via_docker(image: str, tag: str) -> dict:
    """Check arm64 support using docker manifest inspect."""
    full_image = f"{image}:{tag}"
    try:
        result = subprocess.run(
            ["docker", "manifest", "inspect", full_image],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return {
                "image": full_image,
                "arm64_supported": None,
                "error": result.stderr.strip(),
                "architectures": [],
            }

        manifest = json.loads(result.stdout)
        architectures = []

        for m in manifest.get("manifests", []):
            platform = m.get("platform", {})
            arch = platform.get("architecture", "unknown")
            os_name = platform.get("os", "unknown")
            architectures.append(f"{os_name}/{arch}")

        arm64_supported = any("arm64" in a or "aarch64" in a for a in architectures)

        return {
            "image": full_image,
            "arm64_supported": arm64_supported,
            "architectures": architectures,
            "multi_arch": len(architectures) > 1,
        }
    except subprocess.TimeoutExpired:
        return {
            "image": full_image,
            "arm64_supported": None,
            "error": "Timeout checking manifest",
            "architectures": [],
        }
    except Exception as e:
        return {"image": full_image, "arm64_supported": None, "error": str(e), "architectures": []}


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable size."""
    if size_bytes is None:
        return "N/A"
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def format_date(date_str: str) -> str:
    """Format ISO date to readable format."""
    if not date_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else date_str


# =============================================================================
# Command handlers
# =============================================================================


def cmd_search(args):
    """Search for images on Docker Hub."""
    client = DockerHubClient()
    results = client.search(args.query, limit=args.limit)

    if not results:
        console.print(f"[yellow]No results found for '{args.query}'[/yellow]")
        return

    table = Table(title=f"Docker Hub Search: {args.query}")
    table.add_column("Image", style="cyan")
    table.add_column("Stars", justify="right")
    table.add_column("Official", justify="center")
    table.add_column("Description", max_width=50)

    for r in results:
        name = r.get("repo_name", r.get("name", "unknown"))
        stars = str(r.get("star_count", 0))
        official = "✓" if r.get("is_official") else ""
        desc = (r.get("short_description") or "")[:50]

        table.add_row(name, stars, official, desc)

    console.print(table)

    console.print("\n[dim]Tip: Use 'container_images.py tags <image>' to see available tags[/dim]")
    console.print(
        "[dim]     Use 'container_images.py check-arch <image:tag>' to verify arm64 support[/dim]"
    )


def cmd_tags(args):
    """List tags for an image."""
    client = DockerHubClient()

    image = args.image
    if "/" in image:
        namespace, repo = image.split("/", 1)
    else:
        namespace, repo = "library", image

    try:
        tags = client.get_tags(namespace, repo, limit=args.limit)
    except httpx.HTTPStatusError as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    if not tags:
        console.print(f"[yellow]No tags found for '{image}'[/yellow]")
        return

    table = Table(title=f"Tags for {image}")
    table.add_column("Tag", style="cyan")
    table.add_column("Size", justify="right")
    table.add_column("Last Updated")
    table.add_column("Digest", max_width=20)

    for t in tags:
        tag_name = t.get("name", "unknown")
        images = t.get("images", [])
        total_size = sum(img.get("size", 0) for img in images) if images else None
        last_updated = format_date(t.get("last_updated"))
        digest = t.get("digest", "")[:20] if t.get("digest") else ""

        table.add_row(tag_name, format_size(total_size), last_updated, digest)

    console.print(table)


def cmd_check_arch(args):
    """Check architecture support for an image."""
    result = check_arm64_support(args.image)

    if result.get("error"):
        console.print(f"[yellow]Warning: {result['error']}[/yellow]")

    arm64 = result.get("arm64_supported")
    if arm64 is True:
        status = "[green]✓ ARM64 SUPPORTED[/green]"
    elif arm64 is False:
        status = "[red]✗ ARM64 NOT SUPPORTED[/red]"
    else:
        status = "[yellow]? UNKNOWN[/yellow]"

    content = f"""
**Image:** {result["image"]}
**ARM64 Compatible:** {status}
**Multi-arch:** {"Yes" if result.get("multi_arch") else "No"}
**Architectures:** {", ".join(result.get("architectures", [])) or "Unknown"}
"""

    console.print(Panel(Markdown(content), title="Architecture Check"))

    if arm64 is True:
        console.print("\n[green]✓ Safe to deploy on VPS1 (arm64)[/green]")
    elif arm64 is False:
        console.print("\n[red]✗ DO NOT deploy on VPS1 - no arm64 support![/red]")
        console.print("[dim]Look for an alternative image or check if there's an arm64 tag[/dim]")


def cmd_info(args):
    """Get detailed info about an image."""
    client = DockerHubClient()

    image = args.image
    tag = "latest"
    if ":" in image:
        image, tag = image.rsplit(":", 1)

    if "/" in image:
        namespace, repo = image.split("/", 1)
    else:
        namespace, repo = "library", image

    try:
        info = client.get_repository(namespace, repo)
    except httpx.HTTPStatusError as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    arch_result = check_arm64_support(f"{namespace}/{repo}", tag)
    arm64 = arch_result.get("arm64_supported")
    arm64_status = "✓ Yes" if arm64 else ("✗ No" if arm64 is False else "? Unknown")

    content = f"""
## {info.get("namespace", namespace)}/{info.get("name", repo)}

**Description:** {info.get("description", "N/A")}

**Stats:**
- Stars: {info.get("star_count", 0)}
- Pulls: {info.get("pull_count", 0):,}
- Last Updated: {format_date(info.get("last_updated"))}

**ARM64 Support:** {arm64_status}
**Architectures:** {", ".join(arch_result.get("architectures", [])) or "Check specific tag"}

**Links:**
- Hub: https://hub.docker.com/r/{namespace}/{repo}
"""

    console.print(Panel(Markdown(content), title="Image Info"))

    console.print("\n[bold]Recent Tags:[/bold]")
    try:
        tags = client.get_tags(namespace, repo, limit=5)
        for t in tags:
            console.print(f"  - {t.get('name')}")
    except (httpx.HTTPError, ValueError, KeyError) as e:
        console.print(f"  [dim]Unable to fetch tags: {str(e)}[/dim]")
    except Exception as e:
        console.print(f"  [dim]Unexpected error fetching tags: {str(e)}[/dim]")


def cmd_pull(args):
    """Pull an image to local WSL."""
    image = args.image

    result = check_arm64_support(image)

    if result.get("arm64_supported") is False:
        console.print(f"[red]Warning: {image} does not support arm64![/red]")
        if not args.force:
            console.print("[yellow]Use --force to pull anyway (for local testing only)[/yellow]")
            return

    console.print(f"[cyan]Pulling {image}...[/cyan]")

    cmd = ["docker", "pull"]
    if args.platform:
        cmd.extend(["--platform", args.platform])
    cmd.append(image)

    try:
        result = subprocess.run(cmd, check=True)
        console.print(f"[green]✓ Successfully pulled {image}[/green]")
    except subprocess.CalledProcessError:
        console.print(f"[red]✗ Failed to pull {image}[/red]")


def cmd_recommend(args):
    """Get recommendations for common use cases."""
    recommendations = {
        "database": [
            ("postgres:16-alpine", "PostgreSQL - lightweight Alpine variant"),
            ("mariadb:11", "MariaDB - MySQL compatible"),
            ("redis:7-alpine", "Redis - in-memory cache"),
        ],
        "webserver": [
            ("nginx:alpine", "Nginx - lightweight web server"),
            ("traefik:v3", "Traefik - reverse proxy with auto SSL"),
            ("caddy:2-alpine", "Caddy - automatic HTTPS"),
        ],
        "monitoring": [
            ("netdata/netdata", "Netdata - real-time monitoring"),
            ("louislam/uptime-kuma", "Uptime Kuma - status monitoring"),
            ("prom/prometheus", "Prometheus - metrics collection"),
            ("grafana/grafana", "Grafana - dashboards"),
        ],
        "backup": [
            ("lscr.io/linuxserver/duplicati", "Duplicati - cloud backup"),
            ("restic/restic", "Restic - fast backup"),
        ],
        "development": [
            ("lscr.io/linuxserver/code-server", "VS Code in browser"),
            ("gitea/gitea", "Gitea - self-hosted Git"),
        ],
        "media": [
            ("lscr.io/linuxserver/jellyfin", "Jellyfin - media server"),
            ("lscr.io/linuxserver/plex", "Plex - media server"),
        ],
    }

    category = args.category.lower() if args.category else None

    if category and category not in recommendations:
        console.print(f"[yellow]Unknown category: {category}[/yellow]")
        console.print(f"Available: {', '.join(recommendations.keys())}")
        return

    categories = [category] if category else recommendations.keys()

    for cat in categories:
        table = Table(title=f"Recommended: {cat.title()}")
        table.add_column("Image", style="cyan")
        table.add_column("Description")
        table.add_column("ARM64", justify="center")

        for image, desc in recommendations[cat]:
            arm64 = (
                "✓"
                if any(
                    x in image
                    for x in [
                        "alpine",
                        "linuxserver",
                        "netdata",
                        "uptime-kuma",
                        "postgres",
                        "redis",
                        "nginx",
                        "traefik",
                        "grafana",
                        "prometheus",
                        "gitea",
                        "caddy",
                    ]
                )
                else "?"
            )
            table.add_row(image, desc, arm64)

        console.print(table)
        console.print()


# =============================================================================
# TrueForge commands
# =============================================================================


def cmd_trueforge_list(args):
    """List all TrueForge container images."""
    client = TrueForgeClient()

    console.print("[cyan]Fetching TrueForge images from GitHub...[/cyan]")

    try:
        packages = client.list_packages(limit=args.limit)
    except httpx.HTTPStatusError as e:
        console.print(f"[red]Error: {e}[/red]")
        if e.response.status_code == 403:
            console.print(
                "[yellow]Rate limited. Set GITHUB_TOKEN in .env for higher limits.[/yellow]"
            )
        return
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    if not packages:
        console.print("[yellow]No packages found[/yellow]")
        return

    table = Table(title=f"TrueForge Container Images ({len(packages)} found)")
    table.add_column("Image", style="cyan")
    table.add_column("Registry URL")
    table.add_column("Visibility")

    for pkg in packages:
        name = pkg.get("name", "unknown")
        registry_url = f"oci.trueforge.org/tccr/{name}"
        visibility = pkg.get("visibility", "unknown")

        table.add_row(name, registry_url, visibility)

    console.print(table)

    console.print("\n[dim]Pull example: docker pull oci.trueforge.org/tccr/<name>:latest[/dim]")
    console.print(
        "[dim]Check arch:   container_images.py check-arch oci.trueforge.org/tccr/<name>[/dim]"
    )
    console.print("[dim]List tags:    container_images.py trueforge tags <name>[/dim]")


def cmd_trueforge_tags(args):
    """List tags for a TrueForge image."""
    client = TrueForgeClient()

    try:
        versions = client.get_package_versions(args.image, limit=args.limit)
    except httpx.HTTPStatusError as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    if not versions:
        console.print(f"[yellow]No versions found for '{args.image}'[/yellow]")
        return

    table = Table(title=f"TrueForge Tags: {args.image}")
    table.add_column("Tag", style="cyan")
    table.add_column("Created")
    table.add_column("ID", max_width=15)

    for v in versions:
        tags = v.get("metadata", {}).get("container", {}).get("tags", [])
        tag_str = ", ".join(tags) if tags else "(untagged)"
        created = format_date(v.get("created_at"))
        version_id = str(v.get("id", ""))[:15]

        table.add_row(tag_str, created, version_id)

    console.print(table)

    console.print(f"\n[dim]Pull: docker pull oci.trueforge.org/tccr/{args.image}:<tag>[/dim]")


def cmd_trueforge_info(args):
    """Get info about a TrueForge image."""
    client = TrueForgeClient()

    try:
        info = client.get_package_info(args.image)
    except httpx.HTTPStatusError as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    # Check architecture
    arch_result = client.check_arm64_via_oci(args.image)
    arm64 = arch_result.get("arm64_supported")
    arm64_status = "✓ Yes" if arm64 else ("✗ No" if arm64 is False else "? Unknown")

    content = f"""
## {info.get("name", args.image)}

**Registry:** oci.trueforge.org/tccr/{info.get("name", args.image)}
**Visibility:** {info.get("visibility", "N/A")}
**Created:** {format_date(info.get("created_at"))}
**Updated:** {format_date(info.get("updated_at"))}

**ARM64 Support:** {arm64_status}
**Architectures:** {", ".join(arch_result.get("architectures", [])) or "Check specific tag"}

**Links:**
- GitHub: https://github.com/{TRUEFORGE_ORG}/containerforge
- Package: https://github.com/orgs/{TRUEFORGE_ORG}/packages/container/package/{info.get("name", args.image)}

**Supply Chain Security:**
- GitHub Actions attestations
- Verifiable provenance
- SBOM available
"""

    console.print(Panel(Markdown(content), title="TrueForge Image Info"))


# =============================================================================
# Main
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Container Image Discovery Tool for Fabrik",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported Registries:
  - Docker Hub (docker.io)
  - LinuxServer.io (lscr.io)
  - GitHub Container Registry (ghcr.io)
  - TrueForge (oci.trueforge.org)

Examples:
  %(prog)s search nginx                    Search Docker Hub
  %(prog)s tags postgres                   List Docker Hub tags
  %(prog)s check-arch redis:7-alpine       Check arm64 support
  %(prog)s info nginx:alpine               Get image details
  %(prog)s recommend database              Get recommendations
  %(prog)s trueforge list                  List TrueForge images
  %(prog)s trueforge tags home-assistant   List TrueForge image tags
  %(prog)s trueforge info home-assistant   Get TrueForge image info
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Search command
    search_p = subparsers.add_parser("search", help="Search Docker Hub for images")
    search_p.add_argument("query", help="Search query")
    search_p.add_argument("-l", "--limit", type=int, default=15, help="Max results")
    search_p.set_defaults(func=cmd_search)

    # Tags command
    tags_p = subparsers.add_parser("tags", help="List image tags (Docker Hub)")
    tags_p.add_argument("image", help="Image name (e.g., nginx, library/postgres)")
    tags_p.add_argument("-l", "--limit", type=int, default=20, help="Max tags")
    tags_p.set_defaults(func=cmd_tags)

    # Info command
    info_p = subparsers.add_parser("info", help="Get image details (Docker Hub)")
    info_p.add_argument("image", help="Image name with optional tag")
    info_p.set_defaults(func=cmd_info)

    # Check architecture command
    arch_p = subparsers.add_parser("check-arch", help="Check arm64 support (any registry)")
    arch_p.add_argument("image", help="Image name with optional tag")
    arch_p.set_defaults(func=cmd_check_arch)

    # Pull command
    pull_p = subparsers.add_parser("pull", help="Pull image to WSL")
    pull_p.add_argument("image", help="Image to pull")
    pull_p.add_argument("--platform", help="Platform (e.g., linux/arm64)")
    pull_p.add_argument("--force", action="store_true", help="Pull even if arm64 not supported")
    pull_p.set_defaults(func=cmd_pull)

    # Recommend command
    rec_p = subparsers.add_parser("recommend", help="Get image recommendations")
    rec_p.add_argument(
        "category",
        nargs="?",
        help="Category (database, webserver, monitoring, backup, development, media)",
    )
    rec_p.set_defaults(func=cmd_recommend)

    # TrueForge subcommand
    trueforge_p = subparsers.add_parser("trueforge", help="TrueForge/ContainerForge commands")
    trueforge_sub = trueforge_p.add_subparsers(dest="trueforge_cmd", help="TrueForge command")

    # TrueForge list
    tf_list = trueforge_sub.add_parser("list", help="List all TrueForge images")
    tf_list.add_argument("-l", "--limit", type=int, default=100, help="Max results")
    tf_list.set_defaults(func=cmd_trueforge_list)

    # TrueForge tags
    tf_tags = trueforge_sub.add_parser("tags", help="List tags for TrueForge image")
    tf_tags.add_argument("image", help="Image name (e.g., home-assistant)")
    tf_tags.add_argument("-l", "--limit", type=int, default=20, help="Max tags")
    tf_tags.set_defaults(func=cmd_trueforge_tags)

    # TrueForge info
    tf_info = trueforge_sub.add_parser("info", help="Get TrueForge image info")
    tf_info.add_argument("image", help="Image name")
    tf_info.set_defaults(func=cmd_trueforge_info)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "trueforge" and not args.trueforge_cmd:
        trueforge_p.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
