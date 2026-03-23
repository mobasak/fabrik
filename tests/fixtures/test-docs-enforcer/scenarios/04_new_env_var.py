"""Scenario 04: New environment variables."""

import os

API_KEY = os.getenv("API_KEY")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
FEATURE_FLAG = os.getenv("ENABLE_BETA_FEATURES", "false")
