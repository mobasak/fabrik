"""
Coolify API Client - Driver for Coolify deployment platform.

Coolify API v4 documentation: https://coolify.io/docs/api-reference
API Base: http://<ip>:8000/api/v1
"""

import base64
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Literal

import httpx

logger = logging.getLogger(__name__)


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
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 60.0,
        ssh_host: str = "vps",
    ):
        """
        Initialize Coolify client.

        Args:
            base_url: Coolify API URL. Defaults to COOLIFY_API_URL env var
            token: API token. Defaults to COOLIFY_API_TOKEN env var
            timeout: Request timeout in seconds
            ssh_host: SSH host alias for VPS (used when COOLIFY_INTERNAL_URL is set)
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
        self.ssh_host = ssh_host

        # COOLIFY_INTERNAL_URL bypasses Traefik IP allowlist by calling
        # directly through SSH to the container port (e.g. http://localhost:8002).
        # Set this when running from WSL where the public URL is blocked by iptables.
        self._internal_url: str | None = os.getenv("COOLIFY_INTERNAL_URL")
        if self._internal_url:
            self._internal_url = self._internal_url.rstrip("/")
            logger.debug(
                "Coolify client: using SSH proxy via %s → %s", ssh_host, self._internal_url
            )

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self._headers = headers
        self._client = httpx.Client(timeout=timeout, headers=headers)

    def _request_via_ssh(
        self, method: str, url: str, body: dict | None = None, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Proxy an HTTP request through SSH to bypass Traefik IP allowlist."""
        header_args = " ".join(f'-H "{k}: {v}"' for k, v in self._headers.items())
        data_arg = ""
        if body is not None:
            escaped = json.dumps(body).replace("'", "'\\''")
            data_arg = f"-d '{escaped}'"
        # Append query params to URL if present
        if params:
            from urllib.parse import urlencode

            query_string = urlencode(params)
            url = f"{url}?{query_string}"
        cmd = f"curl -s -X {method} {header_args} {data_arg} '{url}'"
        result = subprocess.run(
            ["ssh", self.ssh_host, cmd],
            capture_output=True,
            text=True,
            timeout=int(self.timeout),
            check=False,
        )
        if result.returncode != 0:
            msg = f"SSH proxy request failed: {result.stderr.strip()}"
            raise RuntimeError(msg)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            msg = f"SSH proxy returned non-JSON: {result.stdout[:200]}"
            raise RuntimeError(msg) from exc

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make HTTP request to Coolify API.

        When COOLIFY_INTERNAL_URL is set, proxies the call through SSH
        to bypass Traefik IP allowlist restrictions (WSL → VPS pipeline use case).
        """
        if self._internal_url:
            url = f"{self._internal_url}{endpoint}"
            body = kwargs.get("json")
            params = kwargs.get("params")
            return self._request_via_ssh(method, url, body, params)

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
        List all applications AND services.

        Dockercompose deployments created via `/applications/dockercompose`
        are stored under `/services`, not `/applications`. This method
        merges both so `find_existing(name)` returns either resource type.

        Returns:
            List of application/service dicts (each with 'uuid' and 'name')
        """
        apps = self._request("GET", "/applications") or []
        try:
            services = self._request("GET", "/services") or []
        except httpx.HTTPStatusError:
            services = []
        return list(apps) + list(services)

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
        fqdn: str | None = None,
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
            fqdn: Optional fully-qualified domain name (e.g., https://example.com)

        Returns:
            Created application dict with uuid

        Raises:
            HTTPStatusError: 409 if app already exists (handle as idempotent)
        """
        # Coolify API v4 requires base64-encoded docker_compose_raw
        try:
            docker_compose_b64 = base64.b64encode(docker_compose_raw.encode()).decode()
            logger.info(
                "Encoding docker_compose_raw (length=%d) to base64 (length=%d)",
                len(docker_compose_raw),
                len(docker_compose_b64),
            )
        except Exception as e:
            logger.error("Base64 encoding failed: %s", e)
            raise

        payload = {
            "project_uuid": project_uuid,
            "server_uuid": server_uuid,
            "environment_name": environment_name,
            "docker_compose_raw": docker_compose_b64,
            "name": name,
            "instant_deploy": instant_deploy,
        }

        if description:
            payload["description"] = description
        if destination_uuid:
            payload["destination_uuid"] = destination_uuid
        # NOTE: `fqdn` is NOT accepted by Coolify on either the create
        # endpoint (422) or on PATCH /services/{uuid} (422). The domain
        # must be wired into the compose's Traefik labels (which Fabrik's
        # template renderer already does). The ``fqdn`` argument below is
        # intentionally ignored for that reason, kept only for API
        # compatibility with callers written before this was understood.
        del fqdn  # noqa: F821

        return self._request("POST", "/applications/dockercompose", json=payload)

    def create_git_application(
        self,
        project_uuid: str,
        server_uuid: str,
        environment_uuid: str,
        git_repository: str,
        git_branch: str = "main",
        private_key_uuid: str | None = None,
        build_pack: Literal["dockercompose", "dockerfile", "nixpacks"] = "dockercompose",
        docker_compose_location: str = "/compose.yaml",
        name: str | None = None,
        description: str = "",
        environment_name: str = "production",
        instant_deploy: bool = False,
        ports_exposes: str = "8000",
    ) -> dict[str, Any]:
        """Create an application from a git repository (private or public).

        Uses POST /applications/private-deploy-key for private repos and
        POST /applications for public repos. The private-deploy-key endpoint
        is Coolify's dedicated path for SSH-key-authenticated git clones.

        Args:
            project_uuid: UUID of project to add app to
            server_uuid: UUID of server to deploy on
            environment_uuid: UUID of the environment (required by Coolify)
            git_repository: Git repository URL (e.g. git@github.com:user/repo.git)
            git_branch: Git branch to deploy (default: main)
            private_key_uuid: UUID of the SSH deploy key in Coolify.
                Required for private repos. Omit for public repos.
            build_pack: Build method (default: dockercompose for compose-based deploys)
            docker_compose_location: Path to compose file in repo (default: /compose.yaml)
            name: Application name
            description: Optional description
            environment_name: Environment name (default: production)
            instant_deploy: Deploy immediately after creation (default: False
                for git-sourced apps — the first deploy triggers git pull + build)
            ports_exposes: Exposed ports string (default: "8000")

        Returns:
            Created application dict with uuid

        Raises:
            ValueError: If private_key_uuid is missing for private repos
            HTTPStatusError: On Coolify API errors
        """
        if private_key_uuid:
            # Private repo: use dedicated endpoint
            payload = {
                "project_uuid": project_uuid,
                "server_uuid": server_uuid,
                "environment_name": environment_name,
                "environment_uuid": environment_uuid,
                "private_key_uuid": private_key_uuid,
                "git_repository": git_repository,
                "git_branch": git_branch,
                "build_pack": build_pack,
                "ports_exposes": ports_exposes,
                "instant_deploy": instant_deploy,
            }
            if name:
                payload["name"] = name
            if description:
                payload["description"] = description
            if build_pack == "dockercompose":
                payload["docker_compose_location"] = docker_compose_location
            return self._request("POST", "/applications/private-deploy-key", json=payload)
        else:
            # Public repo: use generic /applications endpoint
            payload = {
                "project_uuid": project_uuid,
                "server_uuid": server_uuid,
                "environment_name": environment_name,
                "environment_uuid": environment_uuid,
                "type": "public",
                "git_repository": git_repository,
                "git_branch": git_branch,
                "build_pack": build_pack,
                "ports_exposes": ports_exposes,
                "instant_deploy": instant_deploy,
            }
            if name:
                payload["name"] = name
            if description:
                payload["description"] = description
            if build_pack == "dockercompose":
                payload["docker_compose_location"] = docker_compose_location
            return self._request("POST", "/applications", json=payload)

    def list_private_keys(self) -> list[dict[str, Any]]:
        """List SSH private keys registered in Coolify.

        Returns:
            List of key dicts with: id, uuid, name, description, is_git_related
        """
        return self._request("GET", "/security/keys")

    def _resolve_resource_base(self, uuid: str) -> str:
        """Resolve whether `uuid` is an application or a service.

        Coolify's `POST /applications/dockercompose` creates a resource that
        is actually addressable via `/services/{uuid}/*`, not
        `/applications/{uuid}/*`. This helper probes both endpoints.

        Returns:
            "applications" or "services"
        """
        cache = getattr(self, "_resource_type_cache", None)
        if cache is None:
            cache = {}
            self._resource_type_cache = cache
        if uuid in cache:
            return cache[uuid]

        # Try /applications first
        try:
            self._request("GET", f"/applications/{uuid}")
            cache[uuid] = "applications"
            return "applications"
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                raise
        # Fall through to /services
        try:
            self._request("GET", f"/services/{uuid}")
            cache[uuid] = "services"
            return "services"
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Neither exists; default to applications so caller gets a clean 404
                return "applications"
            raise

    def update_application(self, uuid: str, **kwargs) -> dict[str, Any]:
        """
        Update application or service settings (auto-routes by UUID).

        Args:
            uuid: Application/Service UUID
            **kwargs: Fields to update (name, fqdn, etc.)
        """
        base = self._resolve_resource_base(uuid)
        return self._request("PATCH", f"/{base}/{uuid}", json=kwargs)

    def delete_application(self, uuid: str, delete_volumes: bool = False) -> dict[str, Any]:
        """Delete application or service (auto-routes by UUID)."""
        params = {"delete_volumes": str(delete_volumes).lower()}
        base = self._resolve_resource_base(uuid)
        if base == "services":
            params["delete_connected_networks"] = "true"
        return self._request("DELETE", f"/{base}/{uuid}", params=params)

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
        params = {"uuid": uuid, "force": str(force).lower()} if force else {"uuid": uuid}
        return self._request("GET", "/deploy", params=params)

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
        Bulk update environment variables (auto-routes to applications or services).

        Coolify v4 doesn't have a bulk endpoint - iterate and update each var individually.
        POST creates new vars, PATCH updates existing ones.

        Args:
            uuid: Application/Service UUID
            env_vars: Dict of key-value pairs
        """
        base = self._resolve_resource_base(uuid)
        results = []
        for key, value in env_vars.items():
            try:
                # Try POST first (create new)
                self._request(
                    "POST",
                    f"/{base}/{uuid}/envs",
                    json={"key": key, "value": value, "is_literal": True},
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 409:
                    # Already exists, use PATCH to update
                    self._request(
                        "PATCH",
                        f"/{base}/{uuid}/envs",
                        json={"key": key, "value": value, "is_literal": True},
                    )
                else:
                    raise
            results.append({"key": key, "status": "updated"})
        return {"updated": len(results)}

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

    def update_service(self, uuid: str, **kwargs) -> dict[str, Any]:
        """
        Update arbitrary fields on a Coolify service (PATCH /services/{uuid}).

        Mirrors :meth:`update_application` for services. Used by
        :mod:`fabrik.drivers.compose_updater` to push a new compose YAML.

        IMPORTANT: ``docker_compose_raw`` MUST be base64-encoded per Coolify
        API contract (see ``docs/LESSONS_LEARNT.md §1``). The caller is
        responsible for encoding; this method does NOT encode on your behalf
        to keep the wire payload transparent and match ``update_application``.

        Args:
            uuid: Service UUID
            **kwargs: Fields to update (e.g. ``docker_compose_raw=<base64>``)

        Returns:
            Coolify API response dict.
        """
        return self._request("PATCH", f"/services/{uuid}", json=kwargs)

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
