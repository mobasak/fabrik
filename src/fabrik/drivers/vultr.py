"""
Vultr API v2 driver for Fabrik.

Thin client over the Vultr REST API v2 (https://www.vultr.com/api/) used by
`fabrik vultr` to provision/destroy VPS for permanent spokes + disposable DR
drills. Covers every compute product line: vc2/vdc/vhf/vhp/voc/vcg via
``/v2/instances``, and vbm (Bare Metal) via ``/v2/bare-metals``.

Auth: ``VULTR_API_KEY`` (Bearer). Loaded from ``/opt/fabrik/.env.sysadmin``
(which ``config.py`` does NOT auto-load) or from the environment.

Ground truth (verified live 2026-06-08 + GoVultr SDK ``master``):
- create instance -> HTTP 202, body ``{"instance": {...}}``; ``main_ip`` is
  ``"0.0.0.0"`` until ready.
- instance status is NON-monotonic: ``status == "active"`` can precede readiness
  while ``power_status == "stopped"`` / ``server_status == "locked"`` (observed
  live at t+23s, ready at t+58s). So readiness requires ALL of:
  ``status==active && power_status==running && server_status==ok && main_ip!="0.0.0.0"``.
- bare metal: body ``{"bare_metal": {...}}``; the struct has NO
  ``power_status``/``server_status`` (and ``ram``/``disk`` are strings,
  ``cpu_count`` not ``vcpu_count``) -> readiness = ``status==active && main_ip set``.
- delete -> HTTP 204. ``tags`` is a list; the singular ``tag`` field is deprecated.
"""

import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

VULTR_API_BASE = "https://api.vultr.com/v2"
SYSADMIN_ENV = Path("/opt/fabrik/.env.sysadmin")
UBUNTU_2404_OS_ID = 2284  # verified live 2026-06-08 (Ubuntu 24.04 LTS x64)
_PER_PAGE_MAX = 500


class VultrError(RuntimeError):
    """A Vultr API error. ``status`` is the HTTP code; ``body`` the parsed payload."""

    def __init__(self, message: str, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class VultrClient:
    """Vultr API v2 client. Retries 5xx only; 4xx fail fast (those are our bug)."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        # config.py only loads the default .env; .env.sysadmin must be loaded here.
        if api_key is None and not os.environ.get("VULTR_API_KEY") and SYSADMIN_ENV.exists():
            load_dotenv(SYSADMIN_ENV)
        self.api_key = api_key or os.environ.get("VULTR_API_KEY")
        if not self.api_key:
            raise ValueError(
                "VULTR_API_KEY is required (set it in /opt/fabrik/.env.sysadmin or the environment)"
            )
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.Client(
            base_url=VULTR_API_BASE,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    # --- lifecycle ---------------------------------------------------------
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "VultrClient":
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    # --- core request ------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Make a request. Retry only on transport errors and 5xx; never on 4xx."""
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._client.request(method, path, json=json, params=params)
            except httpx.RequestError as e:
                last_exc = VultrError(f"Vultr request error on {method} {path}: {e}")
                if attempt < self.max_retries:
                    time.sleep(min(2**attempt, 10))
                    continue
                raise last_exc from e

            if resp.status_code >= 500:
                last_exc = VultrError(
                    f"Vultr {resp.status_code} server error on {method} {path}",
                    resp.status_code,
                    _safe_json(resp),
                )
                if attempt < self.max_retries:
                    time.sleep(min(2**attempt, 10))
                    continue
                raise last_exc

            if resp.status_code >= 400:
                body = _safe_json(resp)
                msg = body.get("error") if isinstance(body, dict) else resp.text
                raise VultrError(
                    f"Vultr {resp.status_code} on {method} {path}: {msg}", resp.status_code, body
                )

            # G10 hardening (2026-06-08): always return a dict for safe `.get()`
            # chaining at the call sites (most callers do `_request(...).get("foo", [])`).
            # 204 No Content (DELETE) and unexpected empty 200 bodies become `{}`
            # rather than `None` — eliminates the latent `AttributeError: 'NoneType'
            # object has no attribute 'get'` that would surface only on a Vultr
            # API regression and is hard to catch in unit tests.
            if resp.status_code == 204 or not resp.content:
                return {}
            return resp.json()

        raise last_exc or VultrError("Vultr request failed")  # defensive; unreachable

    # --- account + catalog (read-only) ------------------------------------
    def get_account(self) -> dict[str, Any]:
        """Return the account object (auth pre-check). Response wraps in ``account``."""
        return self._request("GET", "/account").get("account", {})

    def list_ssh_keys(self) -> list[dict[str, Any]]:
        return self._request("GET", "/ssh-keys", params={"per_page": _PER_PAGE_MAX}).get(
            "ssh_keys", []
        )

    def list_regions(self) -> list[dict[str, Any]]:
        return self._request("GET", "/regions", params={"per_page": _PER_PAGE_MAX}).get(
            "regions", []
        )

    def list_os(self) -> list[dict[str, Any]]:
        return self._request("GET", "/os", params={"per_page": _PER_PAGE_MAX}).get("os", [])

    def list_plans(self, plan_type: str | None = None) -> list[dict[str, Any]]:
        """List Cloud plans (vc2/vdc/vhf/vhp/voc/vcg). Optional ``plan_type`` filter."""
        params: dict[str, Any] = {"per_page": _PER_PAGE_MAX}
        if plan_type:
            params["type"] = plan_type
        return self._request("GET", "/plans", params=params).get("plans", [])

    def list_bare_metal_plans(self) -> list[dict[str, Any]]:
        """List Bare Metal plans (``vbm-*``) — separate endpoint from /plans."""
        return self._request("GET", "/plans-metal", params={"per_page": _PER_PAGE_MAX}).get(
            "plans_metal", []
        )

    # --- instances ---------------------------------------------------------
    def list_instances(self) -> list[dict[str, Any]]:
        return self._request("GET", "/instances", params={"per_page": _PER_PAGE_MAX}).get(
            "instances", []
        )

    def get_instance(self, instance_id: str) -> dict[str, Any]:
        return self._request("GET", f"/instances/{instance_id}").get("instance", {})

    def destroy_instance(self, instance_id: str) -> None:
        self._request("DELETE", f"/instances/{instance_id}")

    def reboot_instance(self, instance_id: str) -> None:
        self._request("POST", f"/instances/{instance_id}/reboot")

    # --- bare metal --------------------------------------------------------
    def list_bare_metals(self) -> list[dict[str, Any]]:
        return self._request("GET", "/bare-metals", params={"per_page": _PER_PAGE_MAX}).get(
            "bare_metals", []
        )

    def get_bare_metal(self, bm_id: str) -> dict[str, Any]:
        return self._request("GET", f"/bare-metals/{bm_id}").get("bare_metal", {})

    def destroy_bare_metal(self, bm_id: str) -> None:
        self._request("DELETE", f"/bare-metals/{bm_id}")

    def reboot_bare_metal(self, bm_id: str) -> None:
        self._request("POST", f"/bare-metals/{bm_id}/reboot")

    # --- unified create / destroy / wait ----------------------------------
    @staticmethod
    def is_bare_metal(plan: str) -> bool:
        """Bare Metal plans are the only ones on the /v2/bare-metals endpoint."""
        return plan.startswith("vbm-")

    def create_instance(
        self,
        *,
        region: str,
        plan: str,
        hostname: str,
        label: str = "",
        os_id: int = UBUNTU_2404_OS_ID,
        sshkey_ids: list[str] | None = None,
        tags: list[str] | None = None,
        enable_ipv6: bool = True,
        **extra: Any,
    ) -> tuple[str, dict[str, Any]]:
        """Create any Vultr server. Dispatches to /v2/bare-metals when ``plan`` is ``vbm-*``.

        Returns ``(kind, obj)`` where ``kind`` is ``"instance"`` or ``"bare_metal"``.
        ``sshkey_ids`` -> the ``sshkey_id`` array; ``tags`` -> the ``tags`` array
        (never the deprecated singular ``tag``). Extra kwargs pass through to the body
        (e.g. ``user_data``, ``backups``, ``mdisk_mode``).
        """
        body: dict[str, Any] = {
            "region": region,
            "plan": plan,
            "os_id": os_id,
            "hostname": hostname,
            "label": label,
            "sshkey_id": list(sshkey_ids or []),
            "tags": list(tags or []),
            "enable_ipv6": enable_ipv6,
        }
        body.update(extra)
        if self.is_bare_metal(plan):
            return "bare_metal", self._request("POST", "/bare-metals", json=body).get(
                "bare_metal", {}
            )
        return "instance", self._request("POST", "/instances", json=body).get("instance", {})

    def destroy(self, kind: str, resource_id: str) -> None:
        """Destroy by kind ('instance' or 'bare_metal')."""
        if kind == "bare_metal":
            self.destroy_bare_metal(resource_id)
        else:
            self.destroy_instance(resource_id)

    def wait_for_active(
        self,
        kind: str,
        resource_id: str,
        *,
        timeout: int = 180,
        interval: int = 10,
    ) -> dict[str, Any]:
        """Poll until the server is genuinely ready; return the final object.

        Instances: ``status==active`` is NOT sufficient — it precedes readiness
        (live: active+stopped+locked at t+23s, ready at t+58s). Require
        ``status==active && power_status==running && server_status==ok && main_ip!="0.0.0.0"``.
        Bare metal has no power/server fields -> ``status==active && main_ip`` set.
        """
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            if kind == "bare_metal":
                last = self.get_bare_metal(resource_id)
                if last.get("status") == "active" and last.get("main_ip") not in (
                    None,
                    "",
                    "0.0.0.0",
                ):
                    return last
            else:
                last = self.get_instance(resource_id)
                if (
                    last.get("status") == "active"
                    and last.get("power_status") == "running"
                    and last.get("server_status") == "ok"
                    and last.get("main_ip") not in (None, "", "0.0.0.0")
                ):
                    return last
            time.sleep(interval)
        raise VultrError(
            f"{kind} {resource_id} not ready within {timeout}s "
            f"(last: status={last.get('status')}, power={last.get('power_status')}, "
            f"server={last.get('server_status')}, main_ip={last.get('main_ip')})"
        )


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:  # noqa: BLE001 - error bodies may be non-JSON
        return {"error": resp.text}
