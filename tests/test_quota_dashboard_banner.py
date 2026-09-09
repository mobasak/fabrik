"""T05 — the box-budget banner's D-191 sentence and its own grader.

`_budget_probe` (`scripts/sysadmin/quota_dashboard.py:1849-1919`) glued the D-191 partition rule into
two adjacent string literals a line grep cannot see — `"... one Sonnet + one "` and `"Haiku seat per
unit plus the Opus authoritative seat(s)."`. This file is the ONE grader that reads the rendered HTML
and asserts that literal is gone and the replacement (the seats-by-`--slices`/`--units` wording) is
there. `tests/test_quota_dashboard.py` (160 KB, untouched by this ticket) never asserted the banner's
prose — only its numbers — so this sentence had no test at all before this file.

`_budget_probe` wraps its whole body in `try/except Exception` (`:1859`/`:1914` at HEAD) and falls
back to `"Box budget unavailable: <exc>"` on ANY failure — including a broken mock. An absence check
run against that fallback string would pass VACUOUSLY (the fallback contains neither the old nor the
new sentence), so every test here asserts the POSITIVE CONTROL `"Box budget (D-189"` first, proving
the mocked probe actually rendered the real banner, before it asserts anything is absent.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

os.environ.setdefault("QUOTA_DASH_BUDGET", "0")  # only ever turned on inside a test below

import pytest

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "quota_dashboard.py"

# the five keys `_budget_probe` reads off the `dispatch_headroom.py --json` payload
# (quota_dashboard.py:1850-1919, per the T04 -> T05 seam) — a minimal payload carrying exactly these.
_PAYLOAD = {
    "caps": {"box_cap": 23, "concurrency_cap": 17},
    "box_caps": {"read_only": 23, "heavy": 12},
    "box_caps_floored": {"read_only": False, "heavy": False},
    "siblings": {"seats": 0, "ok": True},
    "quota": {"ok": True, "active": "a@x", "hottest_pct": 7.0, "eligible": 1},
}


def _load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Import a FRESH module instance (same recipe as tests/test_quota_dashboard.py::_load) so this
    file never imports test internals from that 160 KB suite."""
    monkeypatch.setenv("QUOTA_DASH_OUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("QUOTA_DASH_POINTER", str(tmp_path / "active"))
    spec = importlib.util.spec_from_file_location(f"qd_banner_{tmp_path.name}", _SRC)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class _MockRun:
    """Stands in for `subprocess.run` on the `dispatch_headroom.py --json` shell-out
    (`_budget_probe`, `:1859-1862`) — never a live 45 s probe in a test."""

    def __init__(self, payload: dict) -> None:
        self.stdout = json.dumps(payload)


def test_the_banner_names_the_partition_not_the_old_d191_literal(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd.subprocess, "run", lambda args, **kw: _MockRun(_PAYLOAD))

    html = qd._budget_probe()

    # positive control FIRST: prove the real banner rendered, not the try/except fallback
    # (`"Box budget unavailable: ..."`) — an absence check against the fallback would pass
    # vacuously and prove nothing about the sentence at all.
    assert "Box budget (D-189" in html, html

    # the literal T05 replaces — a line grep could not see it because it spans two adjacent
    # string literals in the source (`quota_dashboard.py:1911-1912` pre-fix)
    assert "one Sonnet + one Haiku" not in html

    # the replacement names the partition: seats sized by --slices for a review loop, by
    # --units (with the three-seat floor) for a grounding/adjudication surface
    assert "<code>--slices</code>" in html
    assert "<code>--units</code>" in html
    assert "three-seat floor" in html
    assert "partitions its files into slices" in html
