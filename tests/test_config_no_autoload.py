"""`fabrik.config` must honour FABRIK_NO_AUTOLOAD=1 (W-f2d483a6).

It called `load_dotenv()` at import, so any test that imported the package — `spec_loader` does —
loaded the hub's WHOLE real `.env` into the pytest process, although the root conftest.py sets
FABRIK_NO_AUTOLOAD=1 exactly to prevent that. Measured: the real EXA/BRAVE/FIRECRAWL/CONTEXT7 keys
were set for the rest of every session from the first such import.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
PROBE = "import os, fabrik.config; print('EXA_API_KEY' in os.environ)"


def _import_config(no_autoload: str | None) -> str:
    env = {k: v for k, v in os.environ.items() if k not in ("EXA_API_KEY", "FABRIK_NO_AUTOLOAD")}
    if no_autoload is not None:
        env["FABRIK_NO_AUTOLOAD"] = no_autoload
    env["PYTHONPATH"] = str(REPO / "src")
    r = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_the_package_import_loads_no_dotenv_under_no_autoload():
    # Control first: this box's .env must actually carry the key, or "not loaded" proves nothing.
    env_file = REPO / ".env"
    # The SAME parser load_dotenv uses, so the skip decision and the real load cannot disagree
    # (a regex missed `KEY = value`, which dotenv loads). Only the key's presence is read.
    if not env_file.is_file() or "EXA_API_KEY" not in dotenv_values(env_file):
        pytest.skip("no EXA_API_KEY in the hub .env — nothing to leak, nothing to measure")
    assert _import_config(None) == "True", "control: without the flag the import loads .env"
    assert _import_config("1") == "False", "FABRIK_NO_AUTOLOAD=1 was ignored by fabrik.config"
