"""
Coolify API Client - Driver for Coolify deployment platform.

Coolify API v4 documentation: https://coolify.io/docs/api-reference
API Base: http://<ip>:8000/api/v1
"""

import os
from dataclasses import dataclass
from typing import Any, Literal

import httpx


@dataclass
class Application:
    """Coolify application representation."""

    uuid: str
    name: str
    fqdn: str | None
    status: str
    type: str
    repository: str | None = None
    branch: str | None = None


@dataclass
class Service:
    """Coolify service representation."""

    uuid: str
    name: str
    type: str
    status: str


class CoolifyClient:
    """
    Coolify API client for deployment management.

    Requires API token with appropriate permissions.
    Generate token in Coolify UI: Settings > Keys & Tokens > API tokens

    Usage:
        coolify = CoolifyClient()

        # List all applications
        apps = coolify.list_applications()

        # Get application details
        app = coolify.get_application("app-uuid")

        # Deploy application
        coolify.deploy("app-uuid")

        # List servers
        servers = coolify.list_servers()
    """

    def __init__(
        self, base_url: str | None = None, token: str | None = None, timeout: float = 60.0
    ):
        """
        Initialize Coolify client.

        Args:
            base_url: Coolify API URL. Defaults to COOLIFY_API_URL env var
            token: API token. Defaults to COOLIFY_API_TOKEN env var
            timeout: Request timeout in seconds
        """
        env_base_url = os.getenv("COOLIFY_API_URL")  # No default - must be configured
        self.base_url: str = base_url if base_url is not None else (env_base_url or "")

        if not self.base_url:
            raise ValueError(
                "Coolify API URL required. Set COOLIFY_API_URL env var or pass base_url parameter."
            )

        token_value = token if token is not None else os.getenv("COOLIFY_API_TOKEN")
        if not token_value:
            raise ValueError(
                "Coolify API token required. Set COOLIFY_API_TOKEN env var "
                "or pass token parameter. Generate at: Coolify UI > Keys & Tokens > API tokens"
            )
        self.token: str = token_value

        # Ensure base URL has /api/v1
        if not self.base_url.endswith("/api/v1"):
            self.base_url = f"{self.base_url.rstrip('/')}/api/v1"

        self.timeout = timeout
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make HTTP request to Coolify API."""
        url = f"{self.base_url}{endpoint}"
        response = self._client.request(method, url, **kwargs)
        response.raise_for_status()

        # Some endpoints return empty response
        if response.status_code == 204 or not response.content:
            return {"success": True}

        return response.json()

    # =========================================================================
    # Health & Version
    # =========================================================================

    def health(self) -> dict[str, Any]:
        """Check Coolify health (no auth required)."""
        # Health endpoint is at /api/health, not /api/v1/health
        url = self.base_url.replace("/api/v1", "/api/health")
        response = self._client.get(url)
        return response.json() if response.status_code == 200 else {"status": "error"}

    def version(self) -> str:
        """Get Coolify version."""
        url = f"{self.base_url}/version"
        response = self._client.get(url)
        return response.text.strip()

    # =========================================================================
    # Servers
    # =========================================================================

    def list_servers(self) -> list[dict[str, Any]]:
        """
        List all servers.

        Returns:
            List of server dicts with: uuid, name, ip, status, etc.
        """
        return self._request("GET", "/servers")

    def get_server(self, uuid: str) -> dict[str, Any]:
        """Get server details by UUID."""
        return self._request("GET", f"/servers/{uuid}")

    def get_server_resources(self, uuid: str) -> list[dict[str, Any]]:
        """Get all resources (apps, services, databases) on a server."""
        return self._request("GET", f"/servers/{uuid}/resources")

    def get_server_domains(self, uuid: str) -> list[dict[str, Any]]:
        """Get all domains configured on a server."""
        return self._request("GET", f"/servers/{uuid}/domains")

    # =========================================================================
    # Projects
    # =========================================================================

    def list_projects(self) -> list[dict[str, Any]]:
        """List all projects."""
        return self._request("GET", "/projects")

    def get_project(self, uuid: str) -> dict[str, Any]:
        """Get project details by UUID."""
        return self._request("GET", f"/projects/{uuid}")

    def create_project(self, name: str, description: str = "") -> dict[str, Any]:
        """
        Create a new project.

        Args:
            name: Project name
            description: Optional description

        Returns:
            Created project dict with uuid
        """
        return self._request("POST", "/projects", json={"name": name, "description": description})

    # =========================================================================
    # Applications
    # =========================================================================

    def list_applications(self) -> list[dict[str, Any]]:
        """
        List all applications.

        Returns:
            List of application dicts
        """
        return self._request("GET", "/applications")

    def get_application(self, uuid: str) -> dict[str, Any]:
        """Get application details by UUID."""
        return self._request("GET", f"/applications/{uuid}")

    def create_application(
        self,
        project_uuid: str,
        server_uuid: str,
        environment_name: str = "production",
        type: Literal["public", "private"] = "public",
        name: str | None = None,
        description: str = "",
        fqdn: str | None = None,
        git_repository: str | None = None,
        git_branch: str = "main",
        build_pack: Literal["nixpacks", "dockerfile", "dockercompose"] = "dockerfile",
        dockerfile_location: str = "/Dockerfile",
        docker_compose_location: str = "/docker-compose.yml",
    ) -> dict[str, Any]:
        """
        Create a new application.

        Args:
            project_uuid: UUID of project to add app to
            server_uuid: UUID of server to deploy on
            environment_name: Environment name (default: production)
            type: Repository type - public or private
            name: Application name
            description: Description
            fqdn: Fully qualified domain name (e.g., https://app.example.com)
            git_repository: Git repository URL
            git_branch: Git branch to deploy
            build_pack: Build method - nixpacks, dockerfile, or dockercompose
            dockerfile_location: Path to Dockerfile
            docker_compose_location: Path to docker-compose.yml

        Returns:
            Created application dict with uuid
        """
        payload = {
            "project_uuid": project_uuid,
            "server_uuid": server_uuid,
            "environment_name": environment_name,
            "type": type,
            "build_pack": build_pack,
        }

        if name:
            payload["name"] = name
        if description:
            payload["description"] = description
        if fqdn:
            payload["fqdn"] = fqdn
        if git_repository:
            payload["git_repository"] = git_repository
            payload["git_branch"] = git_branch
        if build_pack == "dockerfile":
            payload["dockerfile_location"] = dockerfile_location
        if build_pack == "dockercompose":
            payload["docker_compose_location"] = docker_compose_location

        return self._request("POST", "/applications", json=payload)

    def create_dockercompose_application(
        self,
        project_uuid: str,
        server_uuid: str,
        docker_compose_raw: str,
        name: str,
        environment_name: str = "production",
        description: str = "",
        instant_deploy: bool = True,
        destination_uuid: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a Docker Compose application with inline YAML (no git required).

        Uses POST /applications/dockercompose endpoint.

        Args:
            project_uuid: UUID of project to add app to
            server_uuid: UUID of server to deploy on
            docker_compose_raw: Full docker-compose.yaml content as string
            name: Application name (used for container naming)
            environment_name: Environment name (default: production)
            description: Optional description
            instant_deploy: Deploy immediately after creation (default: True)
            destination_uuid: Optional destination UUID

        Returns:
            Created application dict with uuid

        Raises:
            HTTPStatusError: 409 if app already exists (handle as idempotent)
        """
        payload = {
            "project_uuid": project_uuid,
            "server_uuid": server_uuid,
            "environment_name": environment_name,
            "docker_compose_raw": docker_compose_raw,
            "name": name,
            "instant_deploy": instant_deploy,
        }

        if description:
            payload["description"] = description
        if destination_uuid:
            payload["destination_uuid"] = destination_uuid

        return self._request("POST", "/applications/dockercompose", json=payload)

    def update_application(self, uuid: str, **kwargs) -> dict[str, Any]:
        """
        Update application settings.

        Args:
            uuid: Application UUID
            **kwargs: Fields to update (name, fqdn, etc.)
        """
        return self._request("PATCH", f"/applications/{uuid}", json=kwargs)

    def delete_application(self, uuid: str, delete_volumes: bool = False) -> dict[str, Any]:
        """Delete application."""
        params = {"delete_volumes": str(delete_volumes).lower()}
        return self._request("DELETE", f"/applications/{uuid}", params=params)

    # =========================================================================
    # Deployments
    # =========================================================================

    def deploy(self, uuid: str, force: bool = False) -> dict[str, Any]:
        """
        Deploy/redeploy an application.

        Args:
            uuid: Application UUID
            force: Force rebuild (default: False)

        Returns:
            Deployment info with deployment_uuid
        """
        params = {"force": str(force).lower()} if force else {}
        return self._request("POST", f"/applications/{uuid}/deploy", params=params)

    def get_deployments(self, uuid: str) -> list[dict[str, Any]]:
        """Get deployment history for application."""
        return self._request("GET", f"/applications/{uuid}/deployments")

    def get_deployment(self, app_uuid: str, deployment_uuid: str) -> dict[str, Any]:
        """Get specific deployment details."""
        return self._request("GET", f"/applications/{app_uuid}/deployments/{deployment_uuid}")

    def stop_application(self, uuid: str) -> dict[str, Any]:
        """Stop a running application."""
        return self._request("POST", f"/applications/{uuid}/stop")

    def start_application(self, uuid: str) -> dict[str, Any]:
        """Start a stopped application."""
        return self._request("POST", f"/applications/{uuid}/start")

    def restart_application(self, uuid: str) -> dict[str, Any]:
        """Restart an application."""
        return self._request("POST", f"/applications/{uuid}/restart")

    # =========================================================================
    # Environment Variables
    # =========================================================================

    def get_env_vars(self, uuid: str) -> list[dict[str, Any]]:
        """Get environment variables for application."""
        return self._request("GET", f"/applications/{uuid}/envs")

    def create_env_var(
        self, uuid: str, key: str, value: str, is_secret: bool = True, is_build_time: bool = False
    ) -> dict[str, Any]:
        """
        Create environment variable for application.

        Args:
            uuid: Application UUID
            key: Variable name
            value: Variable value
            is_secret: Whether to mask value in UI (default: True)
            is_build_time: Available during build (default: False, runtime only)
        """
        return self._request(
            "POST",
            f"/applications/{uuid}/envs",
            json={
                "key": key,
                "value": value,
                "is_preview": False,
                "is_build_time": is_build_time,
                "is_literal": True,
            },
        )

    def update_env_var(self, uuid: str, env_uuid: str, **kwargs) -> dict[str, Any]:
        """Update an environment variable."""
        return self._request("PATCH", f"/applications/{uuid}/envs/{env_uuid}", json=kwargs)

    def delete_env_var(self, uuid: str, env_uuid: str) -> dict[str, Any]:
        """Delete an environment variable."""
        return self._request("DELETE", f"/applications/{uuid}/envs/{env_uuid}")

    def bulk_update_env_vars(self, uuid: str, env_vars: dict[str, str]) -> dict[str, Any]:
        """
        Bulk update environment variables.

        Args:
            uuid: Application UUID
            env_vars: Dict of key-value pairs
        """
        return self._request(
            "PATCH",
            f"/applications/{uuid}/envs/bulk",
            json={"data": [{"key": k, "value": v} for k, v in env_vars.items()]},
        )

    # =========================================================================
    # Services (One-click services like databases)
    # =========================================================================

    def list_services(self) -> list[dict[str, Any]]:
        """List all services."""
        return self._request("GET", "/services")

    def get_service(self, uuid: str) -> dict[str, Any]:
        """Get service details by UUID."""
        return self._request("GET", f"/services/{uuid}")

    def start_service(self, uuid: str) -> dict[str, Any]:
        """Start a service."""
        return self._request("POST", f"/services/{uuid}/start")

    def stop_service(self, uuid: str) -> dict[str, Any]:
        """Stop a service."""
        return self._request("POST", f"/services/{uuid}/stop")

    def restart_service(self, uuid: str) -> dict[str, Any]:
        """Restart a service."""
        return self._request("POST", f"/services/{uuid}/restart")

    def delete_service(self, uuid: str) -> dict[str, Any]:
        """Delete a service."""
        return self._request("DELETE", f"/services/{uuid}")

    def update_service_env_vars(self, uuid: str, env_vars: dict[str, str]) -> dict[str, Any]:
        """
        Update environment variables for a docker-compose service.

        Args:
            uuid: Service UUID
            env_vars: Dict of key-value pairs
        """
        # Services use different endpoint than applications
        return self._request(
            "PATCH",
            f"/services/{uuid}",
            json={
                "docker_compose_raw": None,  # Keep existing compose
                "environment_variables": env_vars,
            },
        )

    # =========================================================================
    # Databases
    # =========================================================================

    def list_databases(self) -> list[dict[str, Any]]:
        """List all databases."""
        return self._request("GET", "/databases")

    def get_database(self, uuid: str) -> dict[str, Any]:
        """Get database details by UUID."""
        return self._request("GET", f"/databases/{uuid}")

    def create_database(
        self,
        project_uuid: str,
        server_uuid: str,
        environment_name: str = "production",
        type: Literal["postgresql", "mysql", "mariadb", "mongodb", "redis"] = "postgresql",
        name: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Create a new database.

        Args:
            project_uuid: Project UUID
            server_uuid: Server UUID
            environment_name: Environment name
            type: Database type
            name: Database name
            **kwargs: Additional database-specific options
        """
        payload = {
            "project_uuid": project_uuid,
            "server_uuid": server_uuid,
            "environment_name": environment_name,
            "type": type,
            **kwargs,
        }
        if name:
            payload["name"] = name

        return self._request("POST", "/databases", json=payload)

    def start_database(self, uuid: str) -> dict[str, Any]:
        """Start a database."""
        return self._request("POST", f"/databases/{uuid}/start")

    def stop_database(self, uuid: str) -> dict[str, Any]:
        """Stop a database."""
        return self._request("POST", f"/databases/{uuid}/stop")

    def restart_database(self, uuid: str) -> dict[str, Any]:
        """Restart a database."""
        return self._request("POST", f"/databases/{uuid}/restart")

    # =========================================================================
    # Teams
    # =========================================================================

    def list_teams(self) -> list[dict[str, Any]]:
        """List all teams."""
        return self._request("GET", "/teams")

    def get_current_team(self) -> dict[str, Any]:
        """Get current team (based on API token scope)."""
        return self._request("GET", "/teams/current")

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
