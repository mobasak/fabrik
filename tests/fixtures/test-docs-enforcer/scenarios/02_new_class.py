"""Scenario 02: New class with methods."""


class UserService:
    """Service for managing users."""

    def __init__(self, db_url: str) -> None:
        self.db_url = db_url

    def find_by_email(self, email: str) -> dict | None:
        """Find user by email address."""
        return None
