"""Scenario 01: Two new public functions."""


def get_user(user_id: int) -> dict:
    """Retrieve user by ID."""
    return {"id": user_id, "name": "Test User"}


def update_user(user_id: int, data: dict) -> dict:
    """Update user record."""
    return {**data, "id": user_id}
