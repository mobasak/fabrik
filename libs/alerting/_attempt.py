"""One delivery attempt, with the reason it failed.

WHY (2026-08-16 liveness audit): the alerting layer logged exactly one line on total
failure — ``Alert FAILED (all delivery methods): <title>`` — which names neither the
methods tried nor why each one failed. Every alert this box raises (quota drain,
keepalive, CI health, watchdog) funnels through here, so that one line was the whole
diagnostic surface for a delivery path that had been dead for an unknown period.

An attempt therefore carries its own post-mortem: which method, whether it worked,
and a short operator-actionable ``detail``. ``send_alert`` prints every attempt on
total failure, and ``diagnose()`` / ``--selftest`` render the same records.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A Telegram bot token is `<digits>:<~35 url-safe chars>`. An unexpected exception from
# deep inside urllib can carry the request URL — and this text is written straight to the
# operator's log. A diagnosis surface must never become a credential-disclosure surface,
# so anything token-shaped is redacted on the way in.
# No leading \b: the token's most dangerous appearance is inside a URL path
# (`…/bot8751000:AAH…/sendMessage`), where the preceding `t` is a word character and a
# word boundary never matches. Anchoring on the id:secret shape itself is what works.
_TOKEN_RE = re.compile(r"\d{5,}:[A-Za-z0-9_-]{20,}")


def redact(text: str) -> str:
    """Mask anything shaped like a bot token before it reaches a log line."""
    return _TOKEN_RE.sub("<redacted-token>", text)


@dataclass(frozen=True)
class DeliveryAttempt:
    """The outcome of a single delivery method.

    Attributes:
        method: Stable identifier, e.g. ``ssh-apprise`` / ``telegram-direct``.
        ok:     True only when the message was actually accepted by the transport.
        detail: Why. On success a short confirmation; on failure the *actionable*
                cause ("bot token rejected (HTTP 404)"), never a bare exception repr.
        config: Human-readable note about which env vars fed this attempt, so a
                misconfiguration is visible without reading the source.
    """

    method: str
    ok: bool
    detail: str
    config: str = ""

    def render(self) -> str:
        status = "OK" if self.ok else "FAILED"
        line = f"{self.method}: {status} — {redact(self.detail)}"
        if self.config:
            line += f" [{redact(self.config)}]"
        return line
