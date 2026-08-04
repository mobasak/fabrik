"""Access/refresh token issuance."""
from __future__ import annotations

import secrets

TOKENS: dict[str, dict] = {}  # refresh_token -> {"user": ..., "family": ..., "revoked": bool}


class AuthError(Exception):
    pass


def issue(user: str) -> dict:
    family = secrets.token_hex(4)
    refresh_token = secrets.token_hex(16)
    TOKENS[refresh_token] = {"user": user, "family": family, "revoked": False}
    return {"access": secrets.token_hex(16), "refresh": refresh_token}


def refresh(refresh_token: str) -> dict:
    rec = TOKENS.get(refresh_token)
    if rec is None or rec["revoked"]:
        raise AuthError("unknown or revoked refresh token")
    return {"access": secrets.token_hex(16), "refresh": refresh_token}
