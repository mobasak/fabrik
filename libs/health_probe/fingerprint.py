# VENDORED-FROM fabrik-lib health-probe/fingerprint.py @ f21f2123 — byte-identical below this 3-line header; re-vendor, never edit
# ruff: noqa
# fmt: off
"""Key fingerprinting for multi-key API probes."""

import hashlib


def fingerprint(key: str) -> str:
    """Show first 6 chars + SHA1[:6] of an API key for safe logging."""
    if not key:
        return "(empty)"
    h = hashlib.sha1(key.encode(), usedforsecurity=False).hexdigest()[:6]
    return f"{key[:6]}…{h}"
