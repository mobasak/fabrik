"""
Cloudflare R2 Driver - Client for R2 object storage operations.

Provides methods for:
- Generating presigned URLs (upload/download)
- Object operations (put, get, delete, list)
- Bucket management
"""

import os
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Optional, Literal
from urllib.parse import quote, urlencode

import httpx


class R2Client:
    """
    Client for Cloudflare R2 operations.
    
    Uses S3-compatible API with AWS Signature V4.
    """
    
    def __init__(
        self,
        account_id: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        bucket: Optional[str] = None,
        public_url: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize R2 client.
        
        Args:
            account_id: Cloudflare account ID
            access_key_id: R2 access key ID
            secret_access_key: R2 secret access key
            bucket: Default bucket name
            public_url: Public URL for the bucket (if configured)
            timeout: Request timeout in seconds
        """
        self.account_id = account_id or os.getenv("R2_ACCOUNT_ID", "")
        self.access_key_id = access_key_id or os.getenv("R2_ACCESS_KEY_ID", "")
        self.secret_access_key = secret_access_key or os.getenv("R2_SECRET_ACCESS_KEY", "")
        self.bucket = bucket or os.getenv("R2_BUCKET", "")
        self.public_url = public_url or os.getenv("R2_PUBLIC_URL", "")
        self.timeout = timeout
        
        if not all([self.account_id, self.access_key_id, self.secret_access_key]):
            raise ValueError("R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY required")
        
        # R2 endpoint
        self.endpoint = f"https://{self.account_id}.r2.cloudflarestorage.com"
        self.region = "auto"  # R2 uses 'auto' region
        
        self._client = httpx.Client(timeout=timeout)
    
    def _sign(
        self,
        method: str,
        path: str,
        headers: dict,
        query_params: Optional[dict] = None,
        payload_hash: str = "UNSIGNED-PAYLOAD",
    ) -> dict:
        """
        Sign a request using AWS Signature V4.
        
        Returns headers with Authorization.
        """
        now = datetime.now(timezone.utc)
        date_stamp = now.strftime("%Y%m%d")
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        
        # Canonical request components
        headers["x-amz-date"] = amz_date
        headers["x-amz-content-sha256"] = payload_hash
        
        signed_headers = ";".join(sorted(k.lower() for k in headers.keys()))
        canonical_headers = "".join(
            f"{k.lower()}:{v}\n" for k, v in sorted(headers.items())
        )
        
        query_string = ""
        if query_params:
            query_string = "&".join(
                f"{quote(k, safe='')}={quote(str(v), safe='')}"
                for k, v in sorted(query_params.items())
            )
        
        canonical_request = "\n".join([
            method,
            path,
            query_string,
            canonical_headers,
            signed_headers,
            payload_hash,
        ])
        
        # String to sign
        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        string_to_sign = "\n".join([
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ])
        
        # Signing key
        def sign(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()
        
        k_date = sign(f"AWS4{self.secret_access_key}".encode(), date_stamp)
        k_region = sign(k_date, self.region)
        k_service = sign(k_region, "s3")
        k_signing = sign(k_service, "aws4_request")
        
        signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
        
        # Authorization header
        headers["Authorization"] = (
            f"AWS4-HMAC-SHA256 "
            f"Credential={self.access_key_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )
        
        return headers
    
    def health(self) -> dict:
        """Check R2 connection by listing buckets."""
        try:
            path = "/"
            headers = {"Host": f"{self.account_id}.r2.cloudflarestorage.com"}
            headers = self._sign("GET", path, headers)
            
            response = self._client.get(self.endpoint, headers=headers)
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "endpoint": self.endpoint,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def generate_presigned_url(
        self,
        key: str,
        method: Literal["GET", "PUT"] = "GET",
        expires_in: int = 3600,
        content_type: Optional[str] = None,
        bucket: Optional[str] = None,
    ) -> str:
        """
        Generate a presigned URL for upload or download.
        
        Args:
            key: Object key (path in bucket)
            method: GET for download, PUT for upload
            expires_in: URL validity in seconds (max 7 days)
            content_type: Content-Type for PUT requests
            bucket: Bucket name (uses default if not specified)
            
        Returns:
            Presigned URL string
        """
        bucket = bucket or self.bucket
        if not bucket:
            raise ValueError("Bucket name required")
        
        now = datetime.now(timezone.utc)
        date_stamp = now.strftime("%Y%m%d")
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        
        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        credential = f"{self.access_key_id}/{credential_scope}"
        
        # Query parameters for presigned URL
        query_params = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": credential,
            "X-Amz-Date": amz_date,
            "X-Amz-Expires": str(expires_in),
            "X-Amz-SignedHeaders": "host",
        }
        
        if content_type and method == "PUT":
            query_params["X-Amz-SignedHeaders"] = "content-type;host"
        
        # Canonical request
        path = f"/{bucket}/{key}"
        host = f"{self.account_id}.r2.cloudflarestorage.com"
        
        signed_headers = query_params["X-Amz-SignedHeaders"]
        if content_type and method == "PUT":
            canonical_headers = f"content-type:{content_type}\nhost:{host}\n"
        else:
            canonical_headers = f"host:{host}\n"
        
        query_string = "&".join(
            f"{quote(k, safe='')}={quote(str(v), safe='')}"
            for k, v in sorted(query_params.items())
        )
        
        canonical_request = "\n".join([
            method,
            path,
            query_string,
            canonical_headers,
            signed_headers,
            "UNSIGNED-PAYLOAD",
        ])
        
        # String to sign
        string_to_sign = "\n".join([
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ])
        
        # Signing key
        def sign(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()
        
        k_date = sign(f"AWS4{self.secret_access_key}".encode(), date_stamp)
        k_region = sign(k_date, self.region)
        k_service = sign(k_region, "s3")
        k_signing = sign(k_service, "aws4_request")
        
        signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
        
        # Build final URL
        query_params["X-Amz-Signature"] = signature
        final_query = "&".join(
            f"{quote(k, safe='')}={quote(str(v), safe='')}"
            for k, v in sorted(query_params.items())
        )
        
        return f"{self.endpoint}{path}?{final_query}"
    
    def get_public_url(self, key: str) -> str:
        """
        Get public URL for an object (requires public bucket config).
        
        Args:
            key: Object key
            
        Returns:
            Public URL
        """
        if self.public_url:
            return f"{self.public_url.rstrip('/')}/{key}"
        return f"{self.endpoint}/{self.bucket}/{key}"
    
    def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        bucket: Optional[str] = None,
    ) -> dict:
        """
        Upload an object to R2.
        
        Args:
            key: Object key
            data: File bytes
            content_type: MIME type
            bucket: Bucket name
            
        Returns:
            Response info
        """
        bucket = bucket or self.bucket
        path = f"/{bucket}/{key}"
        
        payload_hash = hashlib.sha256(data).hexdigest()
        headers = {
            "Host": f"{self.account_id}.r2.cloudflarestorage.com",
            "Content-Type": content_type,
            "Content-Length": str(len(data)),
        }
        headers = self._sign("PUT", path, headers, payload_hash=payload_hash)
        
        response = self._client.put(
            f"{self.endpoint}{path}",
            content=data,
            headers=headers,
        )
        response.raise_for_status()
        
        return {
            "key": key,
            "bucket": bucket,
            "size": len(data),
            "etag": response.headers.get("ETag", ""),
        }
    
    def get_object(self, key: str, bucket: Optional[str] = None) -> bytes:
        """
        Download an object from R2.
        
        Args:
            key: Object key
            bucket: Bucket name
            
        Returns:
            File bytes
        """
        bucket = bucket or self.bucket
        path = f"/{bucket}/{key}"
        
        headers = {"Host": f"{self.account_id}.r2.cloudflarestorage.com"}
        headers = self._sign("GET", path, headers)
        
        response = self._client.get(f"{self.endpoint}{path}", headers=headers)
        response.raise_for_status()
        
        return response.content
    
    def delete_object(self, key: str, bucket: Optional[str] = None) -> bool:
        """
        Delete an object from R2.
        
        Args:
            key: Object key
            bucket: Bucket name
            
        Returns:
            True if deleted
        """
        bucket = bucket or self.bucket
        path = f"/{bucket}/{key}"
        
        headers = {"Host": f"{self.account_id}.r2.cloudflarestorage.com"}
        headers = self._sign("DELETE", path, headers)
        
        response = self._client.delete(f"{self.endpoint}{path}", headers=headers)
        return response.status_code in (200, 204)
    
    def list_objects(
        self,
        prefix: str = "",
        max_keys: int = 1000,
        bucket: Optional[str] = None,
    ) -> list[dict]:
        """
        List objects in a bucket.
        
        Args:
            prefix: Key prefix filter
            max_keys: Maximum objects to return
            bucket: Bucket name
            
        Returns:
            List of object info dicts
        """
        bucket = bucket or self.bucket
        path = f"/{bucket}"
        
        query_params = {"list-type": "2", "max-keys": str(max_keys)}
        if prefix:
            query_params["prefix"] = prefix
        
        headers = {"Host": f"{self.account_id}.r2.cloudflarestorage.com"}
        headers = self._sign("GET", path, headers, query_params=query_params)
        
        query_string = urlencode(query_params)
        response = self._client.get(
            f"{self.endpoint}{path}?{query_string}",
            headers=headers,
        )
        response.raise_for_status()
        
        # Parse XML response (simplified)
        import re
        content = response.text
        objects = []
        
        for match in re.finditer(r"<Key>([^<]+)</Key>.*?<Size>(\d+)</Size>", content, re.DOTALL):
            objects.append({
                "key": match.group(1),
                "size": int(match.group(2)),
            })
        
        return objects
    
    def close(self):
        """Close the HTTP client."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
