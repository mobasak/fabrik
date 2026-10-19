"""
DNS Client - Wrapper for Site Provisioner service.

This client calls the site-provisioner service at VPS (provision.vps1.ocoron.com),
which provides unified access to both Namecheap and Cloudflare DNS.
"""

import ipaddress
import json
import logging
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any

import httpx

from fabrik.drivers.ssh import _jump_opts, _one_line, _redact, _via, jump_for

logger = logging.getLogger(__name__)

# Docker's own container-name grammar (`[a-zA-Z0-9][a-zA-Z0-9_.-]+`): the name `docker ps` printed is remote
# text, and only a name of
# this shape may reach the second remote command or a log line unquoted (W-9a560686).
_DOCKER_NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]+")


def _is_ip(text: str) -> bool:
    """True only for a bare dotted-quad IPv4 address — what `.NetworkSettings.Networks.<net>.IPAddress` prints.

    IPv4 only, on purpose: `ipaddress.ip_address` accepts an IPv6 scope id, so `fe80::1%@attacker.example` passed
    and became `http://fe80::1%@attacker.example:<port>` — host `attacker.example`, where the request and its
    key would go; and that field never holds an IPv6 address, which the URL would need bracketed anyway.
    """
    try:
        ipaddress.IPv4Address(text)
    except ValueError:
        return False
    return True


class ProvisionerHTTPError(RuntimeError):
    """The site-provisioner answered outside 2xx through the SSH proxy (W-8bb683e6).

    `curl -s` exits 0 on a 4xx/5xx, so the error body used to come back as the call's success; this
    is the SSH path's ``raise_for_status``. ``status`` is the HTTP status; ``body`` the reply
    cleaned of keys and stripped, its first 200 characters, unquoted (for matching); the message
    carries the one-line quoted form, and only the message reaches ``RuntimeError``."""

    def __init__(self, message: str, *, status: int = 0, body: str = "") -> None:
        # defaults only so copy/pickle can rebuild it from args; __dict__ then restores both
        super().__init__(message)
        self.status = status
        self.body = body


# a header value echoed in a reply: the client's key is masked by value, a foreign one by its name —
# `Name: v`, a quoted JSON/repr key (`"Name": "v"`) and `name=v`; the rest of the line goes
_HEADER_SECRET = re.compile(r"(?im)\b(x-api-key|authorization)([\"']?\s*[:=]\s*)\S[^\r\n]*")


def _curl_quoted(value: str, what: str) -> str:
    """*value* as a curl config string: ``"…"`` with ``\\`` then ``"`` escaped.

    CR, LF and NUL are refused, never escaped: curl cuts a header at a raw newline silently, and
    a header holding one is header injection. The message names *what*, never the value — the
    orchestrator's DNS fallback logs this exception.

    Raises:
        ValueError: *value* holds CR, LF or NUL.
    """
    if any(c in value for c in "\r\n\0"):
        raise ValueError(f"{what} holds a CR, LF or NUL character — refused before ssh ran")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


@dataclass
class DNSRecord:
    """DNS record representation."""

    type: str
    name: str
    value: str
    ttl: int = 1800


class DNSClient:
    """
    DNS management client that wraps the Site Provisioner service API.

    The Site Provisioner service is deployed at VPS and handles:
    - Multi-provider DNS authentication (Namecheap, Cloudflare)
    - Rate limiting
    - Safe record merging (doesn't overwrite existing records)

    Usage:
        dns = DNSClient()

        # Add subdomain
        dns.add_subdomain("ocoron.com", "api", "172.93.160.197")

        # Get all records
        records = dns.get_records("ocoron.com")

        # List domains
        domains = dns.list_domains()
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
        ssh_host: str = "vps",
    ):
        """
        Initialize DNS client.

        Args:
            base_url: Site Provisioner URL. Defaults to SITE_PROVISIONER_URL env var
                     or https://provision.vps1.ocoron.com
            api_key: API key sent as X-API-Key header. Defaults to SITE_PROVISIONER_API_KEY
                     env var. If not set, requests are unauthenticated (local/dev only).
            timeout: Request timeout in seconds
            ssh_host: SSH host alias for VPS (used when SITE_PROVISIONER_INTERNAL_URL is set)
        """
        resolved_url: str = (
            base_url
            or os.getenv("SITE_PROVISIONER_URL", "https://provision.vps1.ocoron.com")
            or "https://provision.vps1.ocoron.com"
        )
        self.base_url = resolved_url.rstrip("/")
        self.api_key = api_key or os.getenv("SITE_PROVISIONER_API_KEY")
        self.timeout = timeout
        self.ssh_host = ssh_host

        # SITE_PROVISIONER_INTERNAL_URL bypasses Traefik IP allowlist by calling
        # directly through SSH to the container port (e.g. http://10.0.1.25:8001).
        # Set this when running from WSL where the public URL is blocked by iptables.
        #
        # Coolify recreates containers on every redeploy → the IP changes. Set
        # SITE_PROVISIONER_CONTAINER=<name-prefix> (e.g. "site-provisioner") to
        # have the driver resolve the live IP via `docker inspect` over SSH on
        # each request. Falls back to SITE_PROVISIONER_INTERNAL_URL on miss.
        self._internal_url: str | None = os.getenv("SITE_PROVISIONER_INTERNAL_URL")
        if self._internal_url:
            self._internal_url = self._internal_url.rstrip("/")
            logger.debug("DNS client: using SSH proxy via %s → %s", ssh_host, self._internal_url)
        self._container_prefix: str | None = os.getenv("SITE_PROVISIONER_CONTAINER")
        self._container_port: str = os.getenv("SITE_PROVISIONER_CONTAINER_PORT", "8001")
        self._container_network: str = os.getenv("SITE_PROVISIONER_CONTAINER_NETWORK", "fabrik")
        self._resolved_url_cache: str | None = None

        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        else:
            logger.warning(
                "SITE_PROVISIONER_API_KEY not set — requests will be unauthenticated. "
                "Set SITE_PROVISIONER_API_KEY in .env for production use."
            )
        self._headers = headers
        self._client = httpx.Client(timeout=timeout, headers=headers)

    def _resolve_container_url(self) -> str | None:
        """Resolve the live internal URL via ``docker inspect`` over SSH.

        Returns ``None`` when ``SITE_PROVISIONER_CONTAINER`` is unset or the container can't be
        found or its IP read (caller falls back to ``SITE_PROVISIONER_INTERNAL_URL``). Result is cached per client
        instance — create a fresh ``DNSClient`` after a Coolify redeploy.

        A DEAD ssh path — a timeout, an ``OSError`` running ssh, ssh's own exit 255 (no
        connection, auth, host key) or a kill by signal — is not a miss (W-894fdc5f): with
        ``SITE_PROVISIONER_INTERNAL_URL`` set it is logged and the static URL is used; without it,
        it raises rather than fall through to the public URL this box cannot reach.

        Raises:
            RuntimeError: the ssh path is dead and no ``SITE_PROVISIONER_INTERNAL_URL`` is set
                (the message names the host and the cause, never the command).
        """
        if not self._container_prefix:
            return None
        if self._resolved_url_cache:
            return self._resolved_url_cache
        # Outside the try below: a bad FABRIK_SSH_JUMP_<ALIAS> must fail loud, never be
        # swallowed into the public-URL fallback (W-2b657bee).
        jump_value = jump_for(self.ssh_host)  # read once: the argv and the message name one jump
        jump = _jump_opts(jump_value)

        def run(remote: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["ssh", *jump, self.ssh_host, remote],
                capture_output=True,
                text=True,
                errors="replace",
                stdin=subprocess.DEVNULL,
                timeout=self.timeout,
                check=False,
            )

        # Find full container name by prefix, then read its IP on the
        # shared coolify network (avoids picking the per-app UUID net).
        dead: str | None = None  # why the ssh path is dead, when it is
        try:
            name_proc = run(
                f"sudo docker ps --filter name=^{self._container_prefix} "
                "--format '{{.Names}}' | head -1"
            )
            container = name_proc.stdout.strip()
            if name_proc.returncode == 255 or name_proc.returncode < 0:
                dead = f"rc={name_proc.returncode}: {_one_line(name_proc.stderr)}"
            elif name_proc.returncode != 0 or not container:
                logger.warning(
                    "DNS client: container prefix %r not found on VPS (stderr=%s)",
                    self._container_prefix,
                    _one_line(name_proc.stderr),
                )
                return None
            elif not _DOCKER_NAME.fullmatch(container):
                logger.warning(
                    "DNS client: container prefix %r matched a name docker would not print (%s)",
                    self._container_prefix,
                    _one_line(container, empty="empty"),
                )
                return None
            else:
                fmt = (
                    '{{(index .NetworkSettings.Networks "'
                    + self._container_network
                    + '").IPAddress}}'
                )
                ip_proc = run(f"sudo docker inspect {container} --format '{fmt}'")
                ip = ip_proc.stdout.strip()
                if ip_proc.returncode == 255 or ip_proc.returncode < 0:
                    dead = f"rc={ip_proc.returncode}: {_one_line(ip_proc.stderr)}"
                elif ip_proc.returncode != 0 or not ip or ip == "<no value>":
                    logger.warning(
                        "DNS client: could not resolve %s IP on %s (stderr=%s)",
                        container,
                        self._container_network,
                        _one_line(ip_proc.stderr),
                    )
                    return None
                elif not _is_ip(ip):
                    # the IP is remote text too, and it becomes the request's target host
                    logger.warning(
                        "DNS client: %s on %s printed no IP address (%s)",
                        container,
                        self._container_network,
                        _one_line(ip, empty="empty"),
                    )
                    return None
                else:
                    url = f"http://{ip}:{self._container_port}"
                    self._resolved_url_cache = url
                    logger.debug(
                        "DNS client: resolved %s → %s (container=%s)",
                        self._container_prefix,
                        url,
                        container,
                    )
                    return url
        except subprocess.TimeoutExpired:
            dead = f"no answer in {self.timeout:g}s"
        except OSError as e:  # no ssh binary, not executable, …
            dead = f"{type(e).__name__}: {e.strerror or e}"
        except Exception as e:  # noqa: BLE001
            logger.warning("DNS client: container resolution failed: %s", e)
            return None
        where = f"ssh to {self.ssh_host!r}{_via(jump_value)}"
        if self._internal_url:
            logger.warning(
                "DNS client: %s is dead (%s) — using SITE_PROVISIONER_INTERNAL_URL", where, dead
            )
            return None
        # Raised OUTSIDE the except, so no __context__ carries the command.
        raise RuntimeError(
            f"DNS client: {where} is dead ({dead}) and SITE_PROVISIONER_INTERNAL_URL is unset — "
            "not falling back to the public URL"
        )

    def _request_via_ssh(
        self, method: str, url: str, body: dict | None = None, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Proxy an HTTP request through SSH to bypass Traefik IP allowlist.

        The API key and the body never touch an argv (W-894fdc5f): they reach the remote curl as a
        ``-K -`` config on stdin, so neither appears in a ``ps`` listing on either host. So the ``vps`` alias must
        not set ``StdinNull`` or ``ForkAfterAuthentication`` in ``~/.ssh/config`` — the request
        would then go out keyless — and ``-T`` keeps a ``RequestTTY`` setting from echoing it back.
        """
        # Every argv word is shlex-quoted for the remote shell (W-6a96f699): a `'` in a domain or
        # endpoint broke out of the old hand-quoted URL and ran the rest on the VPS.
        secret = {"X-API-Key"}
        header_args = " ".join(
            f"-H {shlex.quote(f'{k}: {v}')}" for k, v in self._headers.items() if k not in secret
        )
        config = "".join(
            f"header = {_curl_quoted(f'{k}: {v}', k)}\n"
            for k, v in self._headers.items()
            if k in secret
        )
        if body is not None:  # data-raw: a leading `@` never means a file
            config += f"data-raw = {_curl_quoted(json.dumps(body), 'the request body')}\n"
        # Append query params to URL if present
        if params:
            from urllib.parse import urlencode

            query_string = urlencode(params)
            url = f"{url}?{query_string}"
        # -sS: curl's own error stays on stderr (cleaned below); -w appends the HTTP status as the
        # reply's last line, the only way to see it — -f drops the body, --fail-with-body exits 22
        # into the ssh-failure branch with no status (W-8bb683e6)
        cmd = (
            f"curl -sS -X {shlex.quote(method)} {header_args} {shlex.quote(url)} -K - "
            f"-w {shlex.quote(chr(10) + '%{http_code}')}"
        )
        host = self.ssh_host
        jump = jump_for(host)  # read once: the argv and the error text name the same jump
        try:
            result = subprocess.run(
                ["ssh", "-T", *_jump_opts(jump), host, cmd],
                input=config,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=self.timeout,
                check=False,
            )
            timed_out = False
        except subprocess.TimeoutExpired:
            timed_out = True
        if timed_out:
            # Raised OUTSIDE the except (W-6a96f699): TimeoutExpired's str/repr carry the argv, and
            # `cmd` holds `-H "X-API-Key: …"`, which the orchestrator's DNS fallback logs via %s.
            raise subprocess.TimeoutExpired(
                ["ssh", *_jump_opts(jump), host, "<command redacted>"], self.timeout
            )
        if result.returncode != 0:
            raise RuntimeError(
                f"SSH proxy request to {host!r}{_via(jump)} failed (rc={result.returncode}): "
                f"{_one_line(self._clean(result.stderr))}"
            )
        # the rc check above comes FIRST: an aborted transfer leaves `partial\n200` on stdout
        reply_text, sep, code = result.stdout.rpartition("\n")
        if not sep or not re.fullmatch(r"\d{3}", code):
            reply = _one_line(self._clean(result.stdout).strip()[:200], empty="empty reply")
            raise RuntimeError(f"SSH proxy reply carried no HTTP status: {reply}")
        status = int(code)
        if not 200 <= status <= 299:  # raise_for_status's rule: a 3xx without -L is no success
            # masked BEFORE the cut (a key straddling character 200 would otherwise escape it)
            excerpt = self._clean(reply_text).strip()[:200]
            raise ProvisionerHTTPError(
                f"SSH proxy request to {host!r}{_via(jump)} returned HTTP {status}: "
                f"{_one_line(excerpt, empty='empty body')}",
                status=status,
                body=excerpt,
            )
        try:
            return json.loads(reply_text)
        except json.JSONDecodeError as exc:
            # masked BEFORE the cut (a key straddling character 200 would otherwise escape it),
            # then one line: the reply is remote text (W-9a560686)
            reply = _one_line(self._clean(reply_text).strip()[:200], empty="empty reply")
            msg = f"SSH proxy returned non-JSON: {reply}"
            raise RuntimeError(msg) from exc

    def _clean(self, text: str) -> str:
        """*text* with this client's API key masked, then ``_redact``-ed. A remote shell or a
        server error page can echo the request — `-H "X-API-Key: …"` included — and _redact
        cannot mask a `Key: value` header, so the key goes first."""
        if self.api_key:
            text = text.replace(self.api_key, "<redacted>")
        return _redact(_HEADER_SECRET.sub(r"\1\2<redacted>", text))

    def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make HTTP request to Site Provisioner service.

        Resolution order:
        1. SITE_PROVISIONER_CONTAINER → resolve live IP via ``docker inspect`` over SSH.
        2. SITE_PROVISIONER_INTERNAL_URL → static SSH-proxied URL.
        3. Fallback → public Traefik URL (requires IP allowlist hit).
        """
        resolved = self._resolve_container_url() or self._internal_url
        if resolved:
            url = f"{resolved}{endpoint}"
            body = kwargs.get("json")
            params = kwargs.get("params")
            return self._request_via_ssh(method, url, body, params)

        url = f"{self.base_url}{endpoint}"
        response = self._client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # Health & Status
    # =========================================================================

    def health(self) -> dict[str, Any]:
        """Check Site Provisioner service health."""
        return self._request("GET", "/health")

    def get_rate_limit(self) -> dict[str, Any]:
        """Get current rate limit status."""
        return self._request("GET", "/ratelimit")

    # =========================================================================
    # Domain Management
    # =========================================================================

    def list_domains(self) -> list[dict[str, Any]]:
        """
        List all domains in account.

        Returns:
            List of domain info dicts with keys:
            - domain: domain name
            - expires: expiration date
            - autorenew: bool
            - locked: bool
        """
        result = self._request("GET", "/api/domains")
        return result.get("domains", [])

    def get_domain(self, domain: str) -> dict[str, Any]:
        """Get details for specific domain."""
        return self._request("GET", f"/api/domains/{domain}")

    def check_availability(self, domain: str) -> dict[str, Any]:
        """
        Check domain availability for registration across all registrars.

        Args:
            domain: Domain name to check (e.g., "newsite.com")

        Returns:
            Dict with available (bool), prices per registrar, cheapest registrar
        """
        return self._request("POST", "/api/domains/check", json={"domain": domain})

    # =========================================================================
    # DNS Records
    # =========================================================================

    def get_records(self, domain: str) -> list[dict[str, Any]]:
        """
        Get all Cloudflare DNS records for domain.

        Args:
            domain: Domain name (e.g., "ocoron.com")

        Returns:
            List of record dicts with keys: type, name, content, proxied, ttl
        """
        result = self._request("GET", f"/api/cloudflare/dns/{domain}")
        return result.get("records", [])

    def add_subdomain(
        self, domain: str, subdomain: str, ip: str, proxied: bool = False
    ) -> dict[str, Any]:
        """
        Add A record for subdomain via Cloudflare.

        Args:
            domain: Base domain (e.g., "ocoron.com")
            subdomain: Subdomain name (e.g., "api" for api.ocoron.com)
            ip: IP address to point to
            proxied: Whether to proxy through Cloudflare (default False)

        Returns:
            Result dict with success status

        Example:
            dns.add_subdomain("ocoron.com", "api", "172.93.160.197")
        """
        return self._request(
            "POST",
            f"/api/cloudflare/dns/{domain}/subdomain",
            json={"subdomain": subdomain, "ip": ip, "proxied": proxied},
        )

    def add_record(
        self,
        domain: str,
        record_type: str,
        name: str,
        content: str,
        proxied: bool = False,
        ttl: int = 1,
    ) -> dict[str, Any]:
        """
        Add or update a Cloudflare DNS record (idempotent).

        Args:
            domain: Root domain (e.g., "example.com")
            record_type: Record type — A, AAAA, CNAME, MX, TXT, NS, CAA
            name: Record name; use "@" for the root domain
            content: Record value (IP, hostname, text, etc.)
            proxied: Proxy through Cloudflare CDN
            ttl: TTL in seconds; 1 = automatic

        Returns:
            Result dict from site-provisioner
        """
        return self._request(
            "POST",
            f"/api/cloudflare/dns/{domain}",
            json={
                "record_type": record_type,
                "name": name,
                "content": content,
                "proxied": proxied,
                "ttl": ttl,
            },
        )

    def delete_record(self, domain: str, record_type: str, name: str) -> dict[str, Any]:
        """
        Delete a Cloudflare DNS record by type and name.

        Idempotent. The provisioner's route answers an absent record 200
        ``{"action": "not_found", …}``, returned as is. The vps4 DR drill (2026-06-08) also saw
        its HTTP 500 + plain-text ``Internal Server Error`` on a re-run against records ``dig``
        showed gone; the SSH proxy raises that as ``ProvisionerHTTPError`` (status 500, that exact
        body), mapped here to ``{"status": "absent"}``. ⚠️ That plaintext 500 is the provisioner's
        catch-all for ANY unhandled exception (a Cloudflare failure, a missing zone), so this
        mapping can swallow a real failed delete; a typed status from the provisioner retires it
        (requested of site-provisioner, 2026-10-19). Any other HTTP error raises, a 404 included
        (a missing route).

        Args:
            domain: Root domain
            record_type: A, AAAA, CNAME, MX, TXT, NS, CAA
            name: Record name (use "@" for root)

        Returns:
            Result dict from site-provisioner (``{"action": "deleted" | "not_found", …}``), or
            ``{"status": "absent"}`` for the plaintext 500 above.
        """
        try:
            return self._request(
                "DELETE",
                f"/api/cloudflare/dns/{domain}",
                params={"record_type": record_type, "name": name},
            )
        except ProvisionerHTTPError as e:
            # the plaintext-500 shape only (see the docstring: a catch-all); every other HTTP error,
            # and every non-HTTP failure (ssh, config), propagates
            if e.status == 500 and e.body == "Internal Server Error":
                logger.info(
                    "DNS delete_record(%s, %s, %s): record already absent "
                    "(site-provisioner 500 → treating as success)",
                    domain,
                    record_type,
                    name,
                )
                return {"status": "absent"}
            raise

    # =========================================================================
    # Nameservers
    # =========================================================================

    def get_nameservers(self, domain: str) -> list[str]:
        """Get nameservers for domain."""
        result = self._request("GET", f"/api/dns/{domain}/nameservers")
        return result.get("nameservers", [])

    def set_nameservers(self, domain: str, nameservers: list[str]) -> dict[str, Any]:
        """
        Set custom nameservers for domain.

        Use this when migrating to Cloudflare or other DNS provider.

        Args:
            domain: Domain name
            nameservers: List of nameserver hostnames
        """
        return self._request(
            "PUT", f"/api/dns/{domain}/nameservers", json={"nameservers": nameservers}
        )

    # =========================================================================
    # Account
    # =========================================================================

    def get_balance(self) -> dict[str, Any]:
        """Get account balance."""
        return self._request("GET", "/api/account/balance")

    # =========================================================================
    # Cloudflare — Zone Management
    # =========================================================================

    def cloudflare_health(self) -> dict[str, Any]:
        """Check Cloudflare API health via site-provisioner."""
        return self._request("GET", "/api/cloudflare/health")

    def list_zones(self) -> list[dict[str, Any]]:
        """List all Cloudflare zones."""
        result = self._request("GET", "/api/cloudflare/zones")
        return result.get("zones", [])

    def get_zone_status(self, domain: str) -> dict[str, Any]:
        """Get Cloudflare zone status and nameservers."""
        return self._request("GET", f"/api/cloudflare/zones/{domain}/status")

    def get_cloudflare_records(self, domain: str) -> list[dict[str, Any]]:
        """Get all Cloudflare DNS records for domain."""
        result = self._request("GET", f"/api/cloudflare/dns/{domain}")
        return result.get("records", [])

    # =========================================================================
    # Cloudflare — Provisioning (Fabrik deployment workflow)
    # =========================================================================

    def provision(
        self,
        domain: str,
        target_ip: str,
        subdomains: list[str] | None = None,
        enable_dnssec: bool = False,
        enable_tiered_cache: bool = True,
        enable_page_shield: bool = True,
        create_threat_rule: bool = True,
        threat_threshold: int = 50,
        setup_google: bool = False,
        setup_bing: bool = True,
        setup_indexnow: bool = True,
        setup_ga4: bool = False,
        ga4_account_id: str | None = None,
        ga4_timezone: str = "America/Los_Angeles",
        ga4_currency: str = "USD",
        sitemap_url: str | None = None,
    ) -> dict[str, Any]:
        """
        Provision a website — single call for DNS, CDN, WAF, and search engine setup.

        Sequence before every Coolify deploy:
          1. provision() — creates zone, DNS records, security, search engines
          2. check_ready() — poll until ready=true
          3. Deploy to Coolify

        Args:
            domain: Root domain (e.g., "newsite.com")
            target_ip: VPS IP address
            subdomains: Extra subdomains (e.g., ["www", "api"])
            enable_dnssec: Enable DNSSEC
            enable_tiered_cache: Enable Smart Tiered Cache CDN
            enable_page_shield: Enable Page Shield script monitoring
            create_threat_rule: Create WAF rule blocking high threat scores
            threat_threshold: Threat score 0-100 to block at (default 50)
            setup_google: Register with Google Search Console (requires per-domain owner grant)
            setup_bing: Register with Bing Webmaster Tools
            setup_indexnow: Notify IndexNow (Bing/Yandex/Seznam/Naver)
            setup_ga4: Create GA4 property (requires ga4_account_id)
            ga4_account_id: GA4 account ID (required if setup_ga4=True)
            ga4_timezone: GA4 property timezone
            ga4_currency: GA4 property currency
            sitemap_url: Submit to all search engines during provisioning

        Returns:
            Dict with success, zone_id, dns_records, features_enabled,
            google_search_console, bing_webmaster, indexnow, google_analytics.
            GA4 measurement ID: response["google_analytics"]["measurement_id"]
        """
        payload: dict[str, Any] = {
            "target_ip": target_ip,
            "subdomains": subdomains or [],
            "enable_dnssec": enable_dnssec,
            "enable_tiered_cache": enable_tiered_cache,
            "enable_page_shield": enable_page_shield,
            "create_threat_rule": create_threat_rule,
            "threat_threshold": threat_threshold,
            "setup_google": setup_google,
            "setup_bing": setup_bing,
            "setup_indexnow": setup_indexnow,
            "setup_ga4": setup_ga4,
            "ga4_timezone": ga4_timezone,
            "ga4_currency": ga4_currency,
        }
        if ga4_account_id:
            payload["ga4_account_id"] = ga4_account_id
        if sitemap_url:
            payload["sitemap_url"] = sitemap_url
        return self._request("POST", f"/api/cloudflare/zones/{domain}/provision", json=payload)

    def check_ready(self, domain: str) -> dict[str, Any]:
        """
        Check if domain is ready for Coolify deployment.

        Poll this after provision() until ready_for_deployment=true, then deploy to Coolify.

        Args:
            domain: Root domain (e.g., "newsite.com")

        Returns:
            Dict with ready_for_deployment (bool), zone_exists, zone_status, dns_records, features

        Example:
            result = dns.check_ready("newsite.com")
            if result["ready_for_deployment"]:
                # proceed with Coolify deploy
        """
        return self._request("GET", f"/api/cloudflare/zones/{domain}/ready")

    # =========================================================================
    # Website Integrations (GA4, GSC, Bing — persisted by site-provisioner)
    # =========================================================================

    def get_integrations(self, domain: str) -> dict[str, Any]:
        """
        Retrieve stored integration metadata for a domain.

        Returns GA4 measurement ID, GSC verification status, Bing registration,
        IndexNow ping history — all saved automatically during provision().

        Args:
            domain: Root domain (e.g., "example.com")

        Returns:
            Dict with cloudflare_zone_id, google_analytics, google_search_console,
            bing_webmaster, indexnow fields

        Example:
            info = dns.get_integrations("example.com")
            ga4_id = info["google_analytics"]["measurement_id"]  # e.g. "G-XXXXXXXXXX"
        """
        return self._request("GET", f"/api/websites/{domain}/integrations")

    def list_websites(self, has_ga4: bool | None = None) -> list[dict[str, Any]]:
        """
        List all provisioned websites with optional GA4 filter.

        Args:
            has_ga4: If True, return only sites with GA4 setup

        Returns:
            List of website integration dicts
        """
        params: dict[str, Any] = {}
        if has_ga4 is not None:
            params["has_ga4"] = str(has_ga4).lower()
        result = self._request("GET", "/api/websites", params=params)
        return result if isinstance(result, list) else result.get("websites", [])

    def update_sitemap(self, domain: str, sitemap_url: str) -> dict[str, Any]:
        """
        Update sitemap URL and resubmit to Google, Bing, and IndexNow.

        Args:
            domain: Root domain
            sitemap_url: New sitemap URL

        Returns:
            Dict with success and per-engine submission results
        """
        return self._request(
            "PATCH",
            f"/api/websites/{domain}/sitemap",
            params={"sitemap_url": sitemap_url},
        )

    # =========================================================================
    # Domain Registration
    # =========================================================================

    def get_pricing(self, tld: str) -> dict[str, Any]:
        """
        Get registration pricing for a TLD.

        Args:
            tld: Top-level domain (e.g., "com", "net", "io")

        Returns:
            Dict with tld and pricing info
        """
        return self._request("GET", f"/api/domains/pricing/{tld}")

    def register_domain(
        self,
        domain: str,
        years: int = 1,
        nameservers: list[str] | None = None,
        add_whoisguard: bool = True,
        contact: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Register a new domain via site-provisioner.

        site-provisioner selects the registrar internally. Fabrik does not
        need to know which registrar is used.

        Args:
            domain: Domain to register (e.g., "newsite.com")
            years: Registration period in years
            nameservers: Custom nameservers (site-provisioner picks defaults if omitted)
            add_whoisguard: Enable WHOIS privacy
            contact: Registrant contact info dict with keys:
                     FirstName, LastName, Address1, City, StateProvince,
                     PostalCode, Country, Phone, EmailAddress

        Returns:
            Dict with success, domain, registered, domain_id, order_id, charged_amount

        Example:
            dns.register_domain("newsite.com")
        """
        payload: dict[str, Any] = {
            "domain": domain,
            "years": years,
            "add_whoisguard": add_whoisguard,
        }
        if nameservers:
            payload["nameservers"] = nameservers
        if contact:
            payload["contact"] = contact

        return self._request("POST", "/api/domains/register", json=payload)

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


# Convenience function for quick operations
def add_dns_record(domain: str, subdomain: str, ip: str) -> dict[str, Any]:
    """
    Quick helper to add a subdomain record.

    Example:
        from fabrik.drivers.dns import add_dns_record
        add_dns_record("ocoron.com", "api.vps1", "172.93.160.197")
    """
    with DNSClient() as dns:
        return dns.add_subdomain(domain, subdomain, ip)
