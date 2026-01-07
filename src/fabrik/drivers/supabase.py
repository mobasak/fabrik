"""
Supabase Driver - Client for Supabase Auth and Database operations.

Provides methods for:
- Authentication (JWT verification)
- Database operations (files, jobs, tenants)
- Presigned URL generation coordination
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class SupabaseConfig:
    """Supabase configuration."""

    url: str
    anon_key: str
    service_role_key: str

    @classmethod
    def from_env(cls) -> SupabaseConfig:
        """Load config from environment variables."""
        return cls(
            url=os.getenv("SUPABASE_URL", ""),
            anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
            service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        )


class SupabaseClient:
    """
    Client for Supabase operations.

    Uses the Supabase REST API for database operations and
    GoTrue API for authentication.
    """

    def __init__(
        self,
        url: str | None = None,
        anon_key: str | None = None,
        service_role_key: str | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize Supabase client.

        Args:
            url: Supabase project URL
            anon_key: Supabase anon/public key
            service_role_key: Supabase service role key (for admin ops)
            timeout: Request timeout in seconds
        """
        self.url: str = url or os.getenv("SUPABASE_URL") or ""
        self.anon_key: str = anon_key or os.getenv("SUPABASE_ANON_KEY", "") or ""
        self.service_role_key: str = (
            service_role_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or ""
        )
        self.timeout = timeout

        if not self.url:
            raise ValueError("SUPABASE_URL is required")

        # REST API base URL
        self.rest_url = f"{self.url}/rest/v1"
        self.auth_url = f"{self.url}/auth/v1"

        self._client = httpx.Client(timeout=timeout)

    def _headers(self, use_service_role: bool = False) -> dict[str, str]:
        """Get headers for API requests."""
        key = self.service_role_key if use_service_role else self.anon_key
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def health(self) -> dict:
        """Check Supabase connection health."""
        try:
            response = self._client.get(
                f"{self.url}/rest/v1/",
                headers=self._headers(),
            )
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "url": self.url,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # --- Auth Operations ---

    def verify_jwt(self, token: str) -> dict:
        """
        Verify a Supabase JWT and get user info.

        Args:
            token: JWT access token

        Returns:
            User info dict or error
        """
        try:
            response = self._client.get(
                f"{self.auth_url}/user",
                headers={
                    "apikey": self.anon_key,
                    "Authorization": f"Bearer {token}",
                },
            )
            if response.status_code == 200:
                return {"valid": True, "user": response.json()}
            return {"valid": False, "error": response.text}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    # --- Database Operations ---

    def query(
        self,
        table: str,
        select: str = "*",
        filters: dict | None = None,
        limit: int | None = None,
        use_service_role: bool = False,
    ) -> list[dict]:
        """
        Query a table.

        Args:
            table: Table name
            select: Columns to select
            filters: Column filters (eq only for now)
            limit: Max rows to return
            use_service_role: Use service role key for admin access

        Returns:
            List of rows
        """
        url = f"{self.rest_url}/{table}?select={select}"

        if filters:
            for col, val in filters.items():
                url += f"&{col}=eq.{val}"

        if limit:
            url += f"&limit={limit}"

        response = self._client.get(url, headers=self._headers(use_service_role))
        response.raise_for_status()
        return response.json()

    def insert(
        self,
        table: str,
        data: dict | list[dict],
        use_service_role: bool = False,
    ) -> list[dict]:
        """
        Insert row(s) into a table.

        Args:
            table: Table name
            data: Row data or list of rows
            use_service_role: Use service role key

        Returns:
            Inserted row(s)
        """
        url = f"{self.rest_url}/{table}"

        if isinstance(data, dict):
            data = [data]

        response = self._client.post(
            url,
            json=data,
            headers=self._headers(use_service_role),
        )
        response.raise_for_status()
        return response.json()

    def update(
        self,
        table: str,
        data: dict,
        filters: dict,
        use_service_role: bool = False,
    ) -> list[dict]:
        """
        Update row(s) in a table.

        Args:
            table: Table name
            data: Fields to update
            filters: Row filters
            use_service_role: Use service role key

        Returns:
            Updated row(s)
        """
        url = f"{self.rest_url}/{table}?"

        for col, val in filters.items():
            url += f"{col}=eq.{val}&"

        response = self._client.patch(
            url.rstrip("&"),
            json=data,
            headers=self._headers(use_service_role),
        )
        response.raise_for_status()
        return response.json()

    def delete(
        self,
        table: str,
        filters: dict,
        use_service_role: bool = False,
    ) -> list[dict]:
        """
        Delete row(s) from a table.

        Args:
            table: Table name
            filters: Row filters
            use_service_role: Use service role key

        Returns:
            Deleted row(s)
        """
        url = f"{self.rest_url}/{table}?"

        for col, val in filters.items():
            url += f"{col}=eq.{val}&"

        response = self._client.delete(
            url.rstrip("&"),
            headers=self._headers(use_service_role),
        )
        response.raise_for_status()
        return response.json()

    # --- File Metadata Operations ---

    def create_file_record(
        self,
        tenant_id: str,
        filename: str,
        content_type: str,
        size_bytes: int,
        r2_key: str,
        visibility: str = "private",
        uploaded_by: str | None = None,
    ) -> dict:
        """
        Create a file metadata record.

        Args:
            tenant_id: Tenant UUID
            filename: Original filename
            content_type: MIME type
            size_bytes: File size
            r2_key: R2 object key
            visibility: public/private/internal
            uploaded_by: User UUID

        Returns:
            Created file record
        """
        data = {
            "tenant_id": tenant_id,
            "filename": filename,
            "content_type": content_type,
            "size_bytes": size_bytes,
            "r2_key": r2_key,
            "visibility": visibility,
            "status": "pending",
        }
        if uploaded_by:
            data["uploaded_by"] = uploaded_by

        result = self.insert("files", data, use_service_role=True)
        return result[0] if result else {}

    def create_processing_job(
        self,
        file_id: str,
        job_type: str,
        priority: int = 0,
    ) -> dict:
        """
        Create a file processing job.

        Args:
            file_id: File UUID
            job_type: Job type (transcribe, ocr, extract_text, etc.)
            priority: Job priority (higher = sooner)

        Returns:
            Created job record
        """
        data = {
            "file_id": file_id,
            "job_type": job_type,
            "status": "pending",
            "priority": priority,
        }

        result = self.insert("processing_jobs", data, use_service_role=True)
        return result[0] if result else {}

    def claim_next_job(self, job_types: list[str], worker_id: str) -> dict | None:
        """
        Claim the next available job for processing.

        Uses a transaction-safe approach to claim jobs.

        Args:
            job_types: List of job types this worker handles
            worker_id: Unique worker identifier

        Returns:
            Claimed job or None
        """
        # Find pending job
        for job_type in job_types:
            jobs = self.query(
                "processing_jobs",
                filters={"job_type": job_type, "status": "pending"},
                limit=1,
                use_service_role=True,
            )

            if jobs:
                job = jobs[0]
                # Try to claim it
                updated = self.update(
                    "processing_jobs",
                    {"status": "processing", "worker_id": worker_id},
                    {"id": job["id"], "status": "pending"},
                    use_service_role=True,
                )
                if updated:
                    return updated[0]

        return None

    def complete_job(
        self,
        job_id: str,
        success: bool,
        result_data: dict | None = None,
        error_message: str | None = None,
    ) -> dict:
        """
        Mark a job as completed or failed.

        Args:
            job_id: Job UUID
            success: Whether job succeeded
            result_data: Result metadata
            error_message: Error message if failed

        Returns:
            Updated job record
        """
        data: dict[str, Any] = {
            "status": "completed" if success else "failed",
            "completed_at": "now()",
        }
        if result_data:
            data["result_data"] = result_data
        if error_message:
            data["error_message"] = error_message

        result = self.update(
            "processing_jobs",
            data,
            {"id": job_id},
            use_service_role=True,
        )
        return result[0] if result else {}

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
