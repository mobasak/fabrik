#!/usr/bin/env python3
"""
Create WordPress container in Coolify for ocoron.com deployment.

This script is a workaround for missing `fabrik wp provision` command.
It renders the WordPress compose template and creates the Coolify application.
"""

import base64
import os
import secrets
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")


def generate_password(length: int = 32) -> str:
    """Generate secure random password."""
    return secrets.token_urlsafe(length)[:length]


def render_compose_template(site_id: str) -> str:
    """Render WordPress compose template for site."""
    templates_dir = Path(__file__).parent.parent / "templates" / "wordpress" / "base"

    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template("compose-coolify.yaml.j2")

    # Extract domain from site_id (ocoron.com)
    domain = site_id
    name = site_id.replace(".", "-")  # ocoron-com

    # Generate secure passwords
    db_password = generate_password(32)
    db_root_password = generate_password(32)

    context = {
        "domain": domain,
        "name": name,
        "php_version": "php8.2",
        "db_password": db_password,
        "db_root_password": db_root_password,
    }

    rendered = template.render(**context)

    # Save passwords to .env for later use
    env_file = Path(__file__).parent.parent / ".env"
    with open(env_file, "a") as f:
        f.write(f"\n# WordPress passwords for {site_id} (generated {secrets.token_hex(4)})\n")
        f.write(f"WP_{name.upper().replace('-', '_')}_DB_PASSWORD={db_password}\n")
        f.write(f"WP_{name.upper().replace('-', '_')}_DB_ROOT_PASSWORD={db_root_password}\n")

    return rendered


def create_coolify_app(compose_yaml: str, site_id: str) -> dict:
    """Create Coolify dockercompose application."""
    api_url = os.getenv("COOLIFY_API_URL")
    api_token = os.getenv("COOLIFY_API_TOKEN")

    if not api_url or not api_token:
        raise RuntimeError("COOLIFY_API_URL and COOLIFY_API_TOKEN required in .env")

    # Get server UUID
    headers = {"Authorization": f"Bearer {api_token}"}
    servers_resp = httpx.get(f"{api_url}/api/v1/servers", headers=headers, timeout=30)
    servers_resp.raise_for_status()
    servers = servers_resp.json()

    if not servers or not isinstance(servers, list):
        raise RuntimeError("No servers found in Coolify")

    server_uuid = servers[0]["uuid"]

    # Get or create project
    projects_resp = httpx.get(f"{api_url}/api/v1/projects", headers=headers, timeout=30)
    projects_resp.raise_for_status()
    projects = projects_resp.json()

    project_uuid = None
    for project in projects:
        if project.get("name") == "WordPress Sites":
            project_uuid = project["uuid"]
            break

    if not project_uuid:
        # Create project
        project_data = {
            "name": "WordPress Sites",
            "description": "Fabrik-managed WordPress deployments",
        }
        project_resp = httpx.post(
            f"{api_url}/api/v1/projects", headers=headers, json=project_data, timeout=30
        )
        project_resp.raise_for_status()
        project_uuid = project_resp.json()["uuid"]

    # Create dockercompose application
    name = site_id.replace(".", "-")

    # Base64 encode compose YAML as required by Coolify API
    compose_b64 = base64.b64encode(compose_yaml.encode("utf-8")).decode("ascii")

    app_data = {
        "project_uuid": project_uuid,
        "server_uuid": server_uuid,
        "environment_name": "production",
        "docker_compose_raw": compose_b64,
        "name": name,
        "description": f"WordPress site: {site_id}",
        "instant_deploy": True,
    }

    app_resp = httpx.post(
        f"{api_url}/api/v1/applications/dockercompose",
        headers=headers,
        json=app_data,
        timeout=180,  # Increased timeout for container creation
    )

    if app_resp.status_code == 409:
        print(f"⚠️  Application '{name}' already exists")
        return {"status": "exists", "name": name}

    if app_resp.status_code not in (200, 201):
        print(f"❌ Coolify API error: {app_resp.status_code}")
        print(f"Response: {app_resp.text}")
        app_resp.raise_for_status()

    return app_resp.json()


def main():
    if len(sys.argv) < 2:
        print("Usage: python create_wp_container.py <site_id>")
        print("Example: python create_wp_container.py ocoron.com")
        sys.exit(1)

    site_id = sys.argv[1]

    print(f"🔧 Creating WordPress container for {site_id}")

    # Step 1: Render compose template
    print("📝 Rendering compose template...")
    compose_yaml = render_compose_template(site_id)
    print(f"✅ Template rendered ({len(compose_yaml)} bytes)")

    # Step 2: Create Coolify app
    print("🚀 Creating Coolify application...")
    result = create_coolify_app(compose_yaml, site_id)

    if result.get("status") == "exists":
        print(f"✅ Container already exists: {result['name']}")
    else:
        print(f"✅ Coolify application created: {result.get('uuid', 'unknown')}")
        print(f"   Name: {site_id.replace('.', '-')}")
        print(f"   Deployment: {'Started' if result else 'Pending'}")

    print("\n✅ Container creation complete")
    print(f"   Next: fabrik wp apply {site_id}")


if __name__ == "__main__":
    main()
