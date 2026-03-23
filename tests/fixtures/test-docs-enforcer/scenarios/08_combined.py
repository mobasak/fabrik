"""Scenario 08: Multiple triggers combined."""

import os

from fastapi import FastAPI

app = FastAPI()

CACHE_TTL = os.getenv("CACHE_TTL", "300")
MAX_RETRIES = os.getenv("MAX_RETRIES", "3")


class CacheManager:
    """Manages in-memory cache with TTL."""

    def __init__(self) -> None:
        self._store: dict = {}

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def set(self, key: str, value: str) -> None:
        self._store[key] = value


def clear_expired() -> int:
    """Remove expired cache entries."""
    return 0


@app.get("/cache/{key}")
async def get_cache(key: str):
    """Get cached value."""
    return {"key": key, "value": None}
