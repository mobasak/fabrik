"""A SHIM over ``libs/alerting`` — never a second implementation.

This directory once vendored a copy of the alerting package for the kilo-benchmarks scripts. The
copy was the PRE-REPAIR version: it posted the split Telegram credential raw (the 404 that
killed alerting, fixed in ``libs/alerting/telegram.py`` 2026-08-16), keyed its dedup on the title
alone, and did not honour ``TELEGRAM_FULL_BOT_TOKEN`` — while ``pipeline_alert.sh``, the ONE alert
for "the chain never started", resolved ``alerting`` to it (review pass 63, FC6). One source now:
every name is re-exported from ``libs.alerting``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_LIBS = Path(__file__).resolve().parents[3] / "libs"
if str(_LIBS) not in sys.path:
    sys.path.insert(0, str(_LIBS))

from alerting import *  # noqa: E402, F403 - the shim IS the package
from alerting import _is_enabled, send_alert  # noqa: E402, F401 - the two names the callers use
