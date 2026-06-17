"""Deploy helper — DISABLED 2026-06-17.

The legacy Coolify deploy path (`deploy_to_coolify`) is decommissioned: Coolify
was removed from the fleet 2026-05-30, and deploys now run via SSH + Docker Compose
(`fabrik.orchestrator.deployer_ssh`). The original implementation is preserved below,
commented out (not removed), for history. The function is kept (raising a clear error)
so the lazy `from fabrik.deploy import deploy_to_coolify` in cli.py still resolves.
"""

# import logging
# import os
#
# from fabrik.drivers.coolify import CoolifyClient
#
# logger = logging.getLogger(__name__)


def deploy_to_coolify(app_name: str, compose_content: str) -> dict:
    """DISABLED — legacy Coolify deploy. Use the SSH deployer (`deployer_ssh.py`)."""
    raise NotImplementedError(
        "deploy_to_coolify is disabled — Coolify was decommissioned 2026-05-30. "
        "Deploy via SSH + Docker Compose (fabrik apply / deployer_ssh.py)."
    )

    # --- original Coolify implementation, commented out 2026-06-17 (not removed) ---
    # coolify = CoolifyClient()
    #
    # # Get server
    # server_uuid = os.environ.get("COOLIFY_SERVER_UUID")
    # if not server_uuid:
    #     servers = coolify.list_servers()
    #     if not servers:
    #         raise ValueError("No Coolify servers found. Set COOLIFY_SERVER_UUID.")
    #     server_uuid = servers[0]["uuid"]
    #     logger.warning("COOLIFY_SERVER_UUID not set, auto-detected: %s", server_uuid)
    #
    # # Get/create project
    # project_uuid = os.environ.get("COOLIFY_PROJECT_UUID")
    # if not project_uuid:
    #     projects = coolify.list_projects()
    #     proj = next((p for p in projects if p.get("name") == "fabrik"), None)
    #     if proj:
    #         project_uuid = proj["uuid"]
    #     else:
    #         project_uuid = coolify.create_project("fabrik", "Fabrik apps")["uuid"]
    #
    # # Check existing
    # apps = coolify.list_applications()
    # existing = next((a for a in apps if a.get("name") == app_name), None)
    #
    # if existing:
    #     coolify.deploy(existing["uuid"], force=True)
    #     return {"uuid": existing["uuid"], "status": "redeployed"}
    #
    # # Create new
    # result = coolify.create_dockercompose_application(
    #     project_uuid=project_uuid,
    #     server_uuid=server_uuid,
    #     docker_compose_raw=compose_content,
    #     name=app_name,
    #     instant_deploy=True,
    # )
    # return {"uuid": result.get("uuid"), "status": "created"}
