"""Environment-variable configuration (12-factor: env is the only config source)."""
from __future__ import annotations


def load(env: dict) -> dict:
    return {
        "db_url": env.get("DB_URL", ""),
        "poll_secs": int(env.get("POLL_SECS", "30")),
        "batch_size": int(env.get("BATCH_SIZE", "10")),
    }
