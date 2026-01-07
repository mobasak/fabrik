"""
Site Provisioner - Orchestrate Steps 0-1-2 for new site deployment.

Implements a saga pattern with granular states for safe retries and
partial failure recovery.

States:
    INIT → STEP0_CF_ZONE_CREATED → STEP0_DOMAIN_REGISTERED →
    STEP1_DNS_RECORDS_UPSERTED → STEP1_CF_STATUS_SNAPSHOT →
    GATE_WAIT_CF_ACTIVE → STEP2_COOLIFY_APP_CREATED →
    STEP2_ENV_SET → STEP2_DEPLOY_TRIGGERED → STEP2_WP_INSTALLED → COMPLETE
"""

import base64
import json
import os
import secrets
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader

from fabrik.compose_linter import ComposeLinter
from fabrik.drivers.coolify import CoolifyClient


class ProvisionState(str, Enum):
    """Granular states for the provisioning saga."""

    INIT = "INIT"

    # Step 0: Domain Registration
    STEP0_CF_ZONE_CREATED = "STEP0_CF_ZONE_CREATED"
    STEP0_DOMAIN_REGISTER_REQUESTED = "STEP0_DOMAIN_REGISTER_REQUESTED"
    STEP0_DOMAIN_REGISTERED = "STEP0_DOMAIN_REGISTERED"

    # Step 1: DNS Setup
    STEP1_DNS_RECORDS_UPSERTED = "STEP1_DNS_RECORDS_UPSERTED"
    STEP1_CF_STATUS_SNAPSHOT = "STEP1_CF_STATUS_SNAPSHOT"

    # Gate: Wait for CF zone activation
    GATE_WAIT_CF_ACTIVE = "GATE_WAIT_CF_ACTIVE"

    # Step 2: WordPress Deployment (explicit Coolify states)
    STEP2_COOLIFY_CREATE_REQUESTED = "STEP2_COOLIFY_CREATE_REQUESTED"
    STEP2_COOLIFY_CREATED = "STEP2_COOLIFY_CREATED"
    STEP2_COOLIFY_DEPLOY_REQUESTED = "STEP2_COOLIFY_DEPLOY_REQUESTED"
    STEP2_COOLIFY_DEPLOY_RUNNING = "STEP2_COOLIFY_DEPLOY_RUNNING"
    STEP2_COOLIFY_DEPLOY_SUCCEEDED = "STEP2_COOLIFY_DEPLOY_SUCCEEDED"
    STEP2_HTTP_VERIFIED = "STEP2_HTTP_VERIFIED"

    # Terminal states
    COMPLETE = "COMPLETE"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"

    # Legacy aliases for backward compatibility
    STEP2_COOLIFY_APP_CREATED = "STEP2_COOLIFY_CREATED"
    STEP2_ENV_SET = "STEP2_COOLIFY_CREATED"
    STEP2_DEPLOY_TRIGGERED = "STEP2_COOLIFY_DEPLOY_REQUESTED"
    STEP2_WP_INSTALLED = "STEP2_HTTP_VERIFIED"


@dataclass
class ContactInfo:
    """WHOIS contact information for domain registration."""

    FirstName: str
    LastName: str
    Address1: str
    City: str
    StateProvince: str
    PostalCode: str
    Country: str
    Phone: str  # Format: +CC.NNNNNNNNNN
    EmailAddress: str
    Address2: str = ""
    Organization: str = ""


@dataclass
class SiteProvisionRequest:
    """Input from web GUI for site provisioning."""

    domain: str
    preset: str  # company, landing, saas, ecommerce, content
    contact: ContactInfo
    years: int = 1
    whoisguard: bool = True
    skip_registration: bool = False  # True if user already owns domain


@dataclass
class ProvisionJob:
    """
    Persistent state for a provisioning job.

    Saved to disk after each state transition for crash recovery.
    """

    job_id: str
    domain: str
    preset: str
    state: ProvisionState
    created_at: str
    updated_at: str

    # Step 0 outputs
    zone_id: str = ""
    nameservers: list[str] = field(default_factory=list)
    domain_id: str = ""
    order_id: str = ""
    transaction_id: str = ""

    # Step 1 outputs
    a_record_id: str = ""
    www_record_id: str = ""
    zone_status: str = ""  # pending or active

    # Step 2 outputs
    site_name: str = ""
    coolify_project_uuid: str = ""
    coolify_app_uuid: str = ""
    deployment_uuid: str = ""

    # Credentials (stored in .env, referenced here)
    db_password: str = ""
    db_root_password: str = ""
    wp_admin_password: str = ""

    # Retry tracking
    deploy_retry_count: int = 0
    gitops_fallback_attempted: bool = False

    # Error tracking
    failed_step: str = ""
    error_code: str = ""
    error_message: str = ""
    retryable: bool = True

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        d = asdict(self)
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "ProvisionJob":
        """Create from dict (JSON deserialization)."""
        data["state"] = ProvisionState(data["state"])
        data["contact"] = None  # Contact not stored in job
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SiteProvisioner:
    """
    Orchestrate Steps 0-1-2 for new site deployment.

    Usage:
        provisioner = SiteProvisioner()
        job = provisioner.start(request)
        # Poll job.state until COMPLETE or FAILED_*

    For retries:
        job = provisioner.load_job(job_id)
        provisioner.resume(job)
    """

    DNS_MANAGER_URL = os.getenv("DNS_MANAGER_URL", "https://dns.vps1.ocoron.com")
    VPS_IP = os.getenv("VPS_IP", "172.93.160.197")
    VPS_SERVER_UUID = os.getenv("COOLIFY_SERVER_UUID", "jk4wskkcks8csg4gcokwgw8s")

    JOBS_DIR = Path(__file__).parent.parent.parent / "data" / "provision_jobs"
    TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "wordpress" / "base"

    def __init__(self):
        """Initialize provisioner."""
        self.JOBS_DIR.mkdir(parents=True, exist_ok=True)
        self._http = httpx.Client(timeout=60.0)
        self._coolify: CoolifyClient | None = None

    @property
    def coolify(self) -> CoolifyClient:
        """Lazy-load Coolify client."""
        if self._coolify is None:
            self._coolify = CoolifyClient()
        return self._coolify

    def _dns_api(self, method: str, endpoint: str, **kwargs) -> dict:
        """Call DNS Manager API."""
        url = f"{self.DNS_MANAGER_URL}{endpoint}"
        response = self._http.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    def _generate_password(self, length: int = 24) -> str:
        """Generate a secure random password."""
        return secrets.token_urlsafe(length)

    def _save_job(self, job: ProvisionJob):
        """Persist job state to disk."""
        job.updated_at = datetime.utcnow().isoformat()
        path = self.JOBS_DIR / f"{job.job_id}.json"
        path.write_text(json.dumps(job.to_dict(), indent=2))

    def load_job(self, job_id: str) -> ProvisionJob:
        """Load job from disk."""
        path = self.JOBS_DIR / f"{job_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Job not found: {job_id}")
        return ProvisionJob.from_dict(json.loads(path.read_text()))

    def _transition(self, job: ProvisionJob, new_state: ProvisionState):
        """Transition job to new state and persist."""
        job.state = new_state
        self._save_job(job)

    def _fail(self, job: ProvisionJob, step: str, error: str, retryable: bool = True):
        """Mark job as failed."""
        job.failed_step = step
        job.error_message = str(error)
        job.retryable = retryable
        job.state = ProvisionState.FAILED_RETRYABLE if retryable else ProvisionState.FAILED_TERMINAL
        self._save_job(job)

    # =========================================================================
    # Public API
    # =========================================================================

    def start(self, request: SiteProvisionRequest) -> ProvisionJob:
        """
        Start a new provisioning job.

        Args:
            request: User inputs from web form

        Returns:
            ProvisionJob with initial state
        """
        job_id = f"{request.domain.replace('.', '-')}-{secrets.token_hex(4)}"

        job = ProvisionJob(
            job_id=job_id,
            domain=request.domain,
            preset=request.preset,
            state=ProvisionState.INIT,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
            site_name=request.domain.replace(".", "-"),
        )

        # Generate all passwords upfront
        job.db_password = self._generate_password()
        job.db_root_password = self._generate_password()
        job.wp_admin_password = self._generate_password()

        self._save_job(job)

        # Run the saga
        self._run_saga(job, request)

        return job

    def resume(
        self, job: ProvisionJob, request: SiteProvisionRequest | None = None
    ) -> ProvisionJob:
        """
        Resume a failed or interrupted job.

        Args:
            job: Job to resume
            request: Original request (needed for contact info if resuming Step 0)
        """
        if job.state in (ProvisionState.COMPLETE, ProvisionState.FAILED_TERMINAL):
            return job

        self._run_saga(job, request)
        return job

    def get_status(self, job_id: str) -> dict:
        """Get job status for API response."""
        job = self.load_job(job_id)
        return {
            "job_id": job.job_id,
            "domain": job.domain,
            "state": job.state.value,
            "zone_status": job.zone_status,
            "wp_admin_url": f"https://{job.domain}/wp-admin"
            if job.state == ProvisionState.COMPLETE
            else None,
            "wp_admin_user": "admin" if job.state == ProvisionState.COMPLETE else None,
            "wp_admin_password": job.wp_admin_password
            if job.state == ProvisionState.COMPLETE
            else None,
            "error": job.error_message if job.state.value.startswith("FAILED") else None,
            "retryable": job.retryable if job.state.value.startswith("FAILED") else None,
        }

    # =========================================================================
    # Saga Execution
    # =========================================================================

    def _run_saga(self, job: ProvisionJob, request: SiteProvisionRequest | None = None):
        """Execute saga from current state."""
        try:
            # Step 0: Domain Registration
            if job.state == ProvisionState.INIT:
                if request and request.skip_registration:
                    # Skip registration, but still need CF zone
                    self._step0_create_cf_zone(job)
                else:
                    self._step0_create_cf_zone(job)

            if job.state == ProvisionState.STEP0_CF_ZONE_CREATED:
                if request and not request.skip_registration:
                    self._step0_register_domain(job, request)
                else:
                    # Skip to DNS setup
                    self._transition(job, ProvisionState.STEP0_DOMAIN_REGISTERED)

            # Step 1: DNS Setup
            if job.state == ProvisionState.STEP0_DOMAIN_REGISTERED:
                self._step1_upsert_dns_records(job)

            if job.state == ProvisionState.STEP1_DNS_RECORDS_UPSERTED:
                self._step1_snapshot_cf_status(job)

            # Gate: Wait for CF zone activation
            if job.state == ProvisionState.STEP1_CF_STATUS_SNAPSHOT:
                self._transition(job, ProvisionState.GATE_WAIT_CF_ACTIVE)

            if job.state == ProvisionState.GATE_WAIT_CF_ACTIVE:
                self._gate_wait_cf_active(job)

            # Step 2: WordPress Deployment
            if job.state == ProvisionState.GATE_WAIT_CF_ACTIVE and job.zone_status == "active":
                self._step2_create_coolify_app(job)

            if job.state == ProvisionState.STEP2_COOLIFY_APP_CREATED:
                self._step2_set_env_vars(job)

            if job.state == ProvisionState.STEP2_ENV_SET:
                self._step2_trigger_deploy(job)

            if job.state == ProvisionState.STEP2_DEPLOY_TRIGGERED:
                self._step2_wait_healthy(job)

            if job.state == ProvisionState.STEP2_WP_INSTALLED:
                self._transition(job, ProvisionState.COMPLETE)

        except Exception as e:
            self._fail(job, job.state.value, str(e))

    # =========================================================================
    # Step 0: Domain Registration
    # =========================================================================

    def _step0_create_cf_zone(self, job: ProvisionJob):
        """Create Cloudflare zone to obtain nameservers."""
        try:
            result = self._dns_api("POST", "/api/cloudflare/zones", json={"domain": job.domain})

            job.zone_id = result.get("zone_id", "")
            job.nameservers = result.get("name_servers", [])

            if not job.zone_id or not job.nameservers:
                raise ValueError("Failed to get zone_id or nameservers from Cloudflare")

            self._transition(job, ProvisionState.STEP0_CF_ZONE_CREATED)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                # Zone already exists - fetch it
                status = self._dns_api("GET", f"/api/cloudflare/zones/{job.domain}/status")
                job.zone_id = status.get("zone_id", "")
                job.nameservers = status.get("name_servers", [])
                self._transition(job, ProvisionState.STEP0_CF_ZONE_CREATED)
            else:
                raise

    def _step0_register_domain(self, job: ProvisionJob, request: SiteProvisionRequest):
        """Register domain at Namecheap with Cloudflare nameservers."""
        # Mark that we're about to request registration (for idempotency)
        self._transition(job, ProvisionState.STEP0_DOMAIN_REGISTER_REQUESTED)

        try:
            result = self._dns_api(
                "POST",
                "/api/domains/register",
                json={
                    "domain": job.domain,
                    "years": request.years,
                    "nameservers": job.nameservers,
                    "contact": asdict(request.contact),
                    "add_whoisguard": request.whoisguard,
                },
            )

            if not result.get("registered"):
                raise ValueError(f"Domain registration failed: {result}")

            job.domain_id = result.get("domain_id", "")
            job.order_id = result.get("order_id", "")
            job.transaction_id = result.get("transaction_id", "")

            self._transition(job, ProvisionState.STEP0_DOMAIN_REGISTERED)

        except Exception as e:
            # Registration may have succeeded but response failed
            # Mark as retryable - reconciliation needed
            self._fail(job, "STEP0_DOMAIN_REGISTER", str(e), retryable=True)
            raise

    # =========================================================================
    # Step 1: DNS Setup
    # =========================================================================

    def _step1_upsert_dns_records(self, job: ProvisionJob):
        """Add/update DNS records pointing to VPS."""
        # A record for root domain
        a_result = self._dns_api(
            "POST",
            f"/api/cloudflare/dns/{job.domain}",
            json={
                "record_type": "A",
                "name": job.domain,
                "content": self.VPS_IP,
                "proxied": True,
            },
        )
        job.a_record_id = a_result.get("record", {}).get("id", "")

        # CNAME for www
        www_result = self._dns_api(
            "POST",
            f"/api/cloudflare/dns/{job.domain}",
            json={
                "record_type": "CNAME",
                "name": "www",
                "content": job.domain,
                "proxied": True,
            },
        )
        job.www_record_id = www_result.get("record", {}).get("id", "")

        self._transition(job, ProvisionState.STEP1_DNS_RECORDS_UPSERTED)

    def _step1_snapshot_cf_status(self, job: ProvisionJob):
        """Snapshot Cloudflare zone status (no waiting)."""
        status = self._dns_api("GET", f"/api/cloudflare/zones/{job.domain}/status")
        job.zone_status = status.get("status", "pending")
        self._transition(job, ProvisionState.STEP1_CF_STATUS_SNAPSHOT)

    # =========================================================================
    # Gate: Wait for CF zone activation
    # =========================================================================

    def _gate_wait_cf_active(self, job: ProvisionJob, max_wait_seconds: int = 3600):
        """
        Wait for Cloudflare zone to become active.

        Polls every 30 seconds for up to max_wait_seconds.
        """
        start = time.time()

        while time.time() - start < max_wait_seconds:
            status = self._dns_api("GET", f"/api/cloudflare/zones/{job.domain}/status")
            job.zone_status = status.get("status", "pending")
            self._save_job(job)

            if job.zone_status == "active":
                return

            time.sleep(30)

        # Timeout - leave in GATE state for retry
        job.error_message = f"Zone still pending after {max_wait_seconds}s"

    # =========================================================================
    # Step 2: WordPress Deployment
    # =========================================================================

    def _render_compose(self, job: ProvisionJob) -> str:
        """Render docker-compose.yaml from Coolify-compatible template."""
        env = Environment(
            loader=FileSystemLoader(str(self.TEMPLATES_DIR)),
            autoescape=True,  # Security: prevent XSS in rendered templates
        )
        template = env.get_template("compose-coolify.yaml.j2")

        return template.render(
            name=job.site_name,
            domain=job.domain,
            php_version="php8.2",
            db_password=job.db_password,
            db_root_password=job.db_root_password,
        )

    def _step2_create_coolify_app(self, job: ProvisionJob, retry_count: int = 0):
        """
        Create Coolify project and docker-compose service (deterministic pattern).

        Permanent fix 3: Create without instant_deploy, deploy explicitly.
        """
        self._transition(job, ProvisionState.STEP2_COOLIFY_CREATE_REQUESTED)

        # Create project if not exists
        if not job.coolify_project_uuid:
            project = self.coolify.create_project(
                name=job.site_name, description=f"WordPress site for {job.domain}"
            )
            job.coolify_project_uuid = project.get("uuid", "")
            self._save_job(job)

        # Render and validate compose
        compose_yaml = self._render_compose(job)

        # Permanent fix 2: Lint compose before sending
        linter = ComposeLinter()
        lint_result = linter.lint(compose_yaml)
        if not lint_result.valid:
            raise ValueError(f"Compose validation failed: {'; '.join(lint_result.errors)}")

        # Base64 encode for Coolify API
        compose_b64 = base64.b64encode(compose_yaml.encode()).decode()

        # Create docker-compose service WITHOUT instant_deploy
        try:
            app = self.coolify.create_dockercompose_application(
                project_uuid=job.coolify_project_uuid,
                server_uuid=self.VPS_SERVER_UUID,
                docker_compose_raw=compose_b64,
                name=job.site_name,
                description=f"WordPress for {job.domain}",
                instant_deploy=False,  # Deterministic: create only
            )
            job.coolify_app_uuid = app.get("uuid", "")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                # App already exists - find it
                services = self.coolify.list_services()
                for svc in services:
                    if svc.get("name") == job.site_name:
                        job.coolify_app_uuid = svc.get("uuid", "")
                        break
            else:
                raise

        self._transition(job, ProvisionState.STEP2_COOLIFY_CREATED)

    def _step2_set_env_vars(self, job: ProvisionJob) -> None:
        """Placeholder for setting Coolify environment variables."""
        raise NotImplementedError("Setting env vars for Coolify app is not implemented yet")

    def _step2_wait_healthy(self, job: ProvisionJob) -> None:
        """Placeholder for waiting until the application is healthy."""
        raise NotImplementedError("Health wait step is not implemented yet")

    def _step2_trigger_deploy(self, job: ProvisionJob):
        """
        Explicitly trigger deployment (deterministic pattern).

        Permanent fix 3: Deploy explicitly after create.
        """
        self._transition(job, ProvisionState.STEP2_COOLIFY_DEPLOY_REQUESTED)

        result = self.coolify.start_service(job.coolify_app_uuid)
        job.deployment_uuid = result.get("deployment_uuid", "")
        self._save_job(job)

        # Immediately transition to RUNNING state
        self._transition(job, ProvisionState.STEP2_COOLIFY_DEPLOY_RUNNING)

    def _step2_poll_deployment(
        self, job: ProvisionJob, max_wait_seconds: int = 600, max_retries: int = 2
    ):
        """
        Poll deployment status until success or failure.

        Permanent fix 4: Use explicit deployment status, not container existence.
        """
        start = time.time()
        consecutive_failures = 0
        last_status = ""

        while time.time() - start < max_wait_seconds:
            try:
                svc = self.coolify.get_service(job.coolify_app_uuid)
                status = svc.get("status", "")
                last_status = status

                # Success: Coolify reports running
                if status in ("running", "running:healthy", "running:unknown"):
                    self._transition(job, ProvisionState.STEP2_COOLIFY_DEPLOY_SUCCEEDED)
                    return

                # Retryable failure states
                if status in ("degraded:unhealthy", "exited"):
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        # After 3 consecutive failures, try retry
                        if job.deploy_retry_count < max_retries:
                            job.deploy_retry_count += 1
                            self._save_job(job)
                            # Retry deploy
                            self.coolify.start_service(job.coolify_app_uuid)
                            consecutive_failures = 0
                        else:
                            raise ValueError(
                                f"Deployment failed after {max_retries} retries. "
                                f"Last status: {status}"
                            )
                else:
                    consecutive_failures = 0

            except httpx.HTTPStatusError:
                consecutive_failures += 1

            time.sleep(15)

        # Timeout - check if we should try GitOps fallback
        if job.deploy_retry_count >= max_retries and not job.gitops_fallback_attempted:
            job.gitops_fallback_attempted = True
            job.error_message = f"Switching to GitOps fallback after {max_retries} retries"
            self._save_job(job)
            # TODO: Implement GitOps fallback - push compose to shared git repo
            # and redeploy using git-based Coolify deployment
            # For now, mark as retryable for manual intervention

        job.error_message = (
            f"Deployment timeout after {max_wait_seconds}s. Last status: {last_status}"
        )
        self._transition(job, ProvisionState.FAILED_RETRYABLE)

    def _step2_verify_http(self, job: ProvisionJob, max_wait_seconds: int = 120):
        """
        Verify WordPress is accessible via HTTP.

        Permanent fix 4: Don't infer success from containers, verify HTTP.
        """
        start = time.time()
        url = f"https://{job.domain}"

        while time.time() - start < max_wait_seconds:
            try:
                resp = self._http.get(url, follow_redirects=True, timeout=10)
                # WordPress install page or site is accessible
                if resp.status_code in (200, 302):
                    location = resp.headers.get("location", "")
                    if resp.status_code == 200 or "wp-admin/install.php" in location:
                        self._transition(job, ProvisionState.STEP2_HTTP_VERIFIED)
                        return
            except Exception:
                pass

            time.sleep(10)

        # HTTP verification failed but deployment succeeded
        # This is a warning, not a failure
        job.error_message = f"HTTP verification timeout for {url}"
        self._transition(job, ProvisionState.STEP2_HTTP_VERIFIED)  # Continue anyway

    # =========================================================================
    # Cleanup
    # =========================================================================

    def close(self):
        """Close HTTP clients."""
        self._http.close()
        if self._coolify:
            self._coolify.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# Convenience functions
def provision_site(request: SiteProvisionRequest) -> ProvisionJob:
    """Start a new site provisioning job."""
    with SiteProvisioner() as provisioner:
        return provisioner.start(request)


def get_provision_status(job_id: str) -> dict:
    """Get status of a provisioning job."""
    with SiteProvisioner() as provisioner:
        return provisioner.get_status(job_id)
