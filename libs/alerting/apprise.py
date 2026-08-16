"""SSH → VPS Apprise delivery.

Runs: ssh <VPS_HOST> curl -sf -X POST --data-binary @- <APPRISE_URL>/notify
(the JSON body is piped over ssh stdin, never placed on the remote command line).

The two failure modes look identical from the caller and are NOT (measured
2026-08-16): the SSH hop can fail (unreachable host, no key, BatchMode refused →
ssh's own exit 255), or the hop can succeed and the REMOTE curl fail (exit 6 =
`apprise` does not resolve on the VPS — the container is gone or off the network).
:func:`try_send` distinguishes them, because "fix your SSH config" and "the apprise
container is not running" are different jobs.

Env vars:
    ALERT_VPS_HOST    SSH config host alias (default: vps)
    ALERT_APPRISE_URL Internal Apprise URL visible from VPS (default: http://apprise:8000)
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess

from ._attempt import DeliveryAttempt

logger = logging.getLogger(__name__)

VPS_HOST_DEFAULT = "vps"
APPRISE_URL_DEFAULT = "http://apprise:8000"
METHOD = "ssh-apprise"

# curl's documented exit codes, limited to the ones this hop can realistically hit.
_CURL_EXIT = {
    6: "remote curl could not resolve the Apprise host — the container is not"
    " running or not on the VPS network",
    7: "remote curl could not connect to the Apprise port — container down or wrong port",
    22: "Apprise returned an HTTP error (curl -f) — the notify endpoint rejected the payload",
    28: "remote curl timed out talking to Apprise",
}


def try_send(title: str, body: str) -> DeliveryAttempt:
    """Attempt delivery and report the outcome with its cause."""
    vps_host = os.getenv("ALERT_VPS_HOST", VPS_HOST_DEFAULT)
    apprise_url = os.getenv("ALERT_APPRISE_URL", APPRISE_URL_DEFAULT)
    config = f"host={vps_host}, url={apprise_url}"

    payload = json.dumps({"title": title, "body": body})
    notify_url = apprise_url.rstrip("/") + "/notify"

    # CRITICAL: everything after the host is re-joined by ssh into ONE string and
    # run by the REMOTE shell. Passing the JSON payload as an arg there would
    # (a) word-split on its spaces/quotes → a malformed POST for any real alert,
    # and (b) let title/body (often error text) inject commands on the VPS. So
    # the payload never touches the command line: curl reads the body from stdin
    # (`--data-binary @-`), which ssh forwards from our stdin.
    remote_cmd = (
        "curl -sf -X POST -H 'Content-Type: application/json' "
        f"--data-binary @- {shlex.quote(notify_url)}"
    )
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o",
                "ConnectTimeout=5",
                "-o",
                "BatchMode=yes",
                vps_host,
                remote_cmd,
            ],
            input=payload.encode(),
            capture_output=True,
            timeout=12,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return DeliveryAttempt(METHOD, False, "ssh timed out after 12s", config)
    except FileNotFoundError:
        return DeliveryAttempt(METHOD, False, "ssh binary not found on PATH", config)
    except Exception as exc:  # noqa: BLE001 — delivery must never raise into the caller
        return DeliveryAttempt(METHOD, False, f"{type(exc).__name__}: {exc}", config)

    if result.returncode == 0:
        return DeliveryAttempt(METHOD, True, "Apprise accepted the notification", config)

    stderr = result.stderr.decode(errors="replace").strip()[:200]
    if result.returncode == 255:
        # ssh's own failure code — the hop never reached the VPS shell.
        detail = f"ssh could not reach '{vps_host}' (exit 255)"
        if stderr:
            detail += f": {stderr}"
        return DeliveryAttempt(METHOD, False, detail, config)

    hint = _CURL_EXIT.get(result.returncode, "remote command failed")
    detail = f"remote curl exit {result.returncode} — {hint}"
    if stderr:
        detail += f" | stderr: {stderr}"
    return DeliveryAttempt(METHOD, False, detail, config)


def send(title: str, body: str) -> bool:
    """Back-compatible boolean wrapper around :func:`try_send`."""
    attempt = try_send(title, body)
    if not attempt.ok:
        logger.debug("SSH/Apprise delivery failed: %s", attempt.detail)
    return attempt.ok
