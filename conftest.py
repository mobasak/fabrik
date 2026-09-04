"""Root pytest configuration: a test process NEVER carries live alerting into a child.

504 of the 526 subprocess spawns across the nine suites inherit the parent environment (env=None),
and the hub's own `.env` arms Telegram delivery for every script that autoloads it — two graders
DELIVERED real alerts before their throwaway-root forms landed (the FC6 and FE6 disclosures). Muting
the parent once closes the class for every spawn; a test that needs alerting ARMED un-mutes itself
with `monkeypatch.delenv("ALERT_ENABLED")` — the default is silence (B65-9, FF1).
"""

import os


def mute_alerting() -> None:
    """Unconditional: an operator shell exporting ALERT_ENABLED=1 must not make a suite deliver."""
    os.environ["ALERT_ENABLED"] = "0"
    os.environ["FABRIK_NO_AUTOLOAD"] = "1"


mute_alerting()
