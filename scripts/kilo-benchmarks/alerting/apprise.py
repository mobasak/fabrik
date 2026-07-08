"""
SSH → VPS Apprise delivery via the Fabrik docker-run pattern.

Reaches the `apprise` container (on the `fabrik` docker net, no host-port
binding, no host-side DNS for `apprise`) via:

    ssh <VPS_HOST> "sudo docker run --rm --network fabrik curlimages/curl:latest \\
        -sf -X POST -H 'Content-Type: application/json' -d '<payload>' <notify_url>"

This is the canonical Fabrik pattern for reaching services on the `fabrik`
docker network from the VPS host — mirrors provision_grafana.sh:30,
sysadmin/daily-digest.sh:285, sysadmin/system-prompt.txt:37. The previous
implementation SSH'd then curl'd directly from the host, but the host has
no DNS for `apprise` and the container has no host-port binding, so every
alert hit HTTP 000.

We pass ONE shell-quoted string as the remote command (not a list of argv
items) — SSH joins all remote args with spaces before handing them to the
remote shell, so `-H Content-Type: application/json` in argv form gets
split at the space and curl sees a malformed header (curl exit 3).

Env vars:
    ALERT_VPS_HOST    SSH config host alias (default: vps)
    ALERT_APPRISE_URL Internal Apprise URL visible from the fabrik net
                      (default: http://apprise:8000)
"""

import json
import logging
import os
import shlex
import subprocess

logger = logging.getLogger(__name__)

VPS_HOST_DEFAULT = "vps"
APPRISE_URL_DEFAULT = "http://apprise:8000"


def send(title: str, body: str) -> bool:
    """Send via SSH → docker-run on the fabrik network. Returns True on success.

    Fail-soft: any subprocess non-zero exit or exception returns False; never raises.
    """
    vps_host = os.getenv("ALERT_VPS_HOST", VPS_HOST_DEFAULT)
    apprise_url = os.getenv("ALERT_APPRISE_URL", APPRISE_URL_DEFAULT)

    payload = json.dumps({"title": title, "body": body})
    notify_url = apprise_url.rstrip("/") + "/notify"

    # Build a shell-quoted remote command (SEE module docstring for WHY).
    remote_cmd = (
        "sudo docker run --rm --network fabrik curlimages/curl:latest "
        "-sf -X POST -H 'Content-Type: application/json' "
        f"-d {shlex.quote(payload)} {shlex.quote(notify_url)}"
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
            capture_output=True,
            timeout=15,
        )
        if result.returncode == 0:
            return True
        logger.debug(
            "SSH/docker-run/Apprise non-zero exit %d: %s",
            result.returncode,
            result.stderr.decode(errors="replace")[:200],
        )
        return False
    except Exception as exc:
        logger.debug("SSH/docker-run/Apprise exception: %s", exc)
        return False
