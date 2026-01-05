"""Deploy helper for fabrik apply command."""

import os

from fabrik.drivers.coolify import CoolifyClient


def deploy_to_coolify(app_name: str, compose_content: str) -> dict:
    """Deploy app to Coolify. Returns {uuid, status, action}."""
    coolify = CoolifyClient()

    # Get server
    server_uuid = os.environ.get("COOLIFY_SERVER_UUID")
    if not server_uuid:
        servers = coolify.list_servers()
        server_uuid = servers[0]["uuid"] if servers else None
    if not server_uuid:
        raise ValueError("No server. Set COOLIFY_SERVER_UUID.")

    # Get/create project
    project_uuid = os.environ.get("COOLIFY_PROJECT_UUID")
    if not project_uuid:
        projects = coolify.list_projects()
        proj = next((p for p in projects if p.get("name") == "fabrik"), None)
        if proj:
            project_uuid = proj["uuid"]
        else:
            project_uuid = coolify.create_project("fabrik", "Fabrik apps")["uuid"]

    # Check existing
    apps = coolify.list_applications()
    existing = next((a for a in apps if a.get("name") == app_name), None)

    if existing:
        coolify.deploy(existing["uuid"], force=True)
        return {"uuid": existing["uuid"], "status": "redeployed"}

    # Create new
    result = coolify.create_dockercompose_application(
        project_uuid=project_uuid,
        server_uuid=server_uuid,
        docker_compose_raw=compose_content,
        name=app_name,
        instant_deploy=True,
    )
    return {"uuid": result.get("uuid"), "status": "created"}
