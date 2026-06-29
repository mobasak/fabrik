"""
SSH → VPS Apprise delivery.

Runs: ssh <VPS_HOST> curl -s -X POST <APPRISE_URL>/notify -H 'Content-Type: application/json' -d '{...}'

Env vars:
    ALERT_VPS_HOST    SSH config host alias (default: vps)
    ALERT_APPRISE_URL Internal Apprise URL visible from VPS (default: http://apprise:8000)
"""

import json
import logging
import os
import subprocess

logger = logging.getLogger(__name__)

VPS_HOST_DEFAULT = "vps"
APPRISE_URL_DEFAULT = "http://apprise:8000"


def send(title: str, body: str) -> bool:
    """Send via SSH to VPS Apprise. Returns True on success."""
    vps_host = os.getenv("ALERT_VPS_HOST", VPS_HOST_DEFAULT)
    apprise_url = os.getenv("ALERT_APPRISE_URL", APPRISE_URL_DEFAULT)

    payload = json.dumps({"title": title, "body": body})
    notify_url = apprise_url.rstrip("/") + "/notify"

    try:
        result = subprocess.run(
            [
                "ssh",
                "-o",
                "ConnectTimeout=5",
                "-o",
                "BatchMode=yes",
                vps_host,
                "curl",
                "-sf",
                "-X",
                "POST",
                "-H",
                "Content-Type: application/json",
                "-d",
                payload,
                notify_url,
            ],
            capture_output=True,
            timeout=12,
        )
        if result.returncode == 0:
            return True
        logger.debug(
            "SSH/Apprise non-zero exit %d: %s",
            result.returncode,
            result.stderr.decode(errors="replace")[:200],
        )
        return False
    except Exception as exc:
        logger.debug("SSH/Apprise exception: %s", exc)
        return False
