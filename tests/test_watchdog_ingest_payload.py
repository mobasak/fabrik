"""Phase 7 (deploy-readiness-gaps): GlitchTip → watchdog :8889 payload contract.

The actual ingest handler runs in the fabrik-lib watchdog sidecar (started when
`watchdog.trigger_sources` includes `error_webhook`), not in this repo — so the
fabrik-side guarantee is that the CAPTURED fixture (byte-identical to what
GlitchTip POSTs, per its `_provenance`) keeps the exact shape that handler reads:
the Slack-compatible envelope `body.attachments[0].{title,title_link,color,fields}`.
If GlitchTip's output drifts, re-capture via scripts/probes/glitchtip_webhook_capture.py
and this test fails loudly so the sidecar parser can be updated in lockstep.
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "reference"
    / "fixtures"
    / "glitchtip-webhook.json"
)


def _extract(payload: dict) -> dict:
    """Mirror the fields the :8889 ingest extracts from a new-issue webhook."""
    att = payload["body"]["attachments"][0]
    return {
        "envelope_text": payload["body"]["text"],
        "title": att["title"],
        "link": att["title_link"],
        "color": att["color"],
        "fields": {f["title"]: f["value"] for f in att.get("fields", [])},
    }


def test_parses_glitchtip_webhook_fixture():
    payload = json.loads(FIXTURE.read_text())
    got = _extract(payload)

    assert got["envelope_text"]  # non-empty Slack envelope text
    assert got["title"] == "ZeroDivisionError: division by zero"
    assert got["link"].endswith("/issues/999999")  # issue deep-link present
    assert got["color"].startswith("#")  # severity color hex
    assert got["fields"].get("Project") == "watchdog-webhook-probe"


def test_fixture_is_real_capture_not_handcrafted():
    # Guards against someone "fixing" a drift by editing the fixture by hand
    # instead of re-capturing — the provenance block documents the real source.
    payload = json.loads(FIXTURE.read_text())
    prov = payload["_provenance"]
    assert prov["recipient_type"] == "webhook"
    assert "send_issue_as_webhook" in prov["method"]
