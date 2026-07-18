"""Env isolation — the package autoloads .env at import; without this tests read the real env."""

import os

os.environ["FABRIK_NO_AUTOLOAD"] = "1"
os.environ.setdefault("SUBAGENTS_ENV_FILE", "/nonexistent/subagents.env.test-sentinel")
