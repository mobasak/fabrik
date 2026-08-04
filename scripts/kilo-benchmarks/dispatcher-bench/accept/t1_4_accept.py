import pytest
from app import auth


def test_refresh_rotates_token():
    t = auth.issue("u1")
    t2 = auth.refresh(t["refresh"])
    assert t2["refresh"] != t["refresh"]
    t3 = auth.refresh(t2["refresh"])
    assert t3["refresh"] != t2["refresh"]


def test_reuse_of_rotated_token_revokes_family():
    t = auth.issue("u2")
    t2 = auth.refresh(t["refresh"])
    with pytest.raises(auth.AuthError):
        auth.refresh(t["refresh"])  # reuse of the rotated token
    with pytest.raises(auth.AuthError):
        auth.refresh(t2["refresh"])  # whole family revoked after reuse
