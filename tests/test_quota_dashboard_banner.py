"""T05 — the box-budget line's numbers, from one probe to the Overview's Health strip.

`_budget_probe` once glued the D-191 partition rule into two adjacent string literals a line grep
could not see (`"... one Sonnet + one "` + `"Haiku seat per unit plus the Opus authoritative
seat(s)."`). The redesign (plan 2026-10-17-plan-1, T03/T07) moved the line onto the Overview's Health
strip as data the view renders through the catalogue, and retired the sizing prose with the old
banner (the seat rules live in `.windsurf/rules/core/62-using-subagents.md`, not on the board). This
file now pins what the line still promises: the probe's numbers reach the view, and the old literal
appears nowhere — not in the catalogue, not on the page.

`_budget_probe` wraps its whole body in `try/except Exception` and falls back to ``{"error": …}`` on
ANY failure — including a broken mock. An absence check run against that fallback would pass
VACUOUSLY, so every test here asserts the POSITIVE CONTROL first: the mocked probe's own numbers
are on the page.
"""

from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path

os.environ.setdefault("QUOTA_DASH_BUDGET", "0")  # only ever turned on inside a test below

import pytest

from tests.quota_dashboard_isolation import (  # noqa: E402, F401
    after_load,
    isolate,
    no_network,  # noqa: E402, F401 — autouse network guard
)

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "quota_dashboard.py"

# the five keys `_budget_probe` reads off the `dispatch_headroom.py --json` payload — a minimal
# payload carrying exactly these.
_PAYLOAD = {
    "caps": {"box_cap": 23, "concurrency_cap": 17},
    "box_caps": {"read_only": 23, "heavy": 12},
    "box_caps_floored": {"read_only": False, "heavy": False},
    "siblings": {"seats": 0, "ok": True},
    "quota": {"ok": True, "active": "a@x", "hottest_pct": 7.0, "eligible": 1},
}


def _load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Import a FRESH module instance (same recipe as tests/test_quota_dashboard.py::_load)."""
    monkeypatch.setenv("QUOTA_DASH_OUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("QUOTA_DASH_POINTER", str(tmp_path / "active"))
    isolate(tmp_path, monkeypatch)  # tests/quota_dashboard_isolation.py
    spec = importlib.util.spec_from_file_location(f"qd_banner_{tmp_path.name}", _SRC)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    after_load(mod, monkeypatch)
    return mod


class _MockRun:
    """Stands in for `subprocess.run` on the `dispatch_headroom.py --json` shell-out — never a live
    45 s probe in a test."""

    def __init__(self, payload: dict) -> None:
        self.stdout = json.dumps(payload)


def test_the_probes_numbers_reach_the_health_strip_and_the_old_d191_literal_is_gone(
    tmp_path, monkeypatch
):
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd.subprocess, "run", lambda args, **kw: _MockRun(_PAYLOAD))
    monkeypatch.setenv("QUOTA_DASH_BUDGET", "1")
    monkeypatch.setattr(qd, "_status_triggers", lambda: None)  # never a quota probe
    reading = qd._budget_probe()
    assert [s["allowed"] for s in reading["seats"]] == [17, 12], reading
    assert qd._budget_data() == reading  # the cache serves the view what the probe read
    qd._set_last_status(time.time(), {"active": "a", "accounts": []})
    html = qd._render_view("overview")
    health = html.split('id="ov-health"', 1)[1]
    # positive control FIRST: the probe's own numbers, not the fallback, are on the strip
    assert "Box budget:" in health and "CLI cap 17" in health, health[:600]
    assert "allowed now: 17" in health and "allowed now: 12" in health
    assert "quota: active a@x at 7.0%" in health
    # the literal T05 replaced, and the sizing prose the redesign retired, appear nowhere
    from dashboard_ui import strings

    for gone in ("one Sonnet + one Haiku", "partitions its files into slices"):
        assert gone not in html
        assert not any(gone in v for v in strings.CATALOGUE.values()), gone
