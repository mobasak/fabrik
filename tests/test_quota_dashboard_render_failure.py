"""W-6a0f3c65 — a regeneration that raises must not leave a fresh-looking page.

On 2026-09-07 the board froze for 16 regeneration cycles on a TypeError: the traceback went to a log
nobody reads, and the page kept saying "updated <old time> · refreshes every 20s". These tests make
`render` raise and assert what a viewer is SERVED, through `_fresh_html()` — the function `do_GET`
calls — never through internal state.
"""

from __future__ import annotations

import importlib.util
import os
import re
import time
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "quota_dashboard.py"
_MARKER = 'id="render-failed"'


def _load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, max_age: str = "0"):
    """A fresh module whose env-derived paths point at tmp_path (the tests/test_quota_dashboard.py
    pattern). MAX_AGE_S=0 makes every view past the floor, so each view regenerates."""
    monkeypatch.setenv("QUOTA_DASH_OUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("QUOTA_DASH_POINTER", str(tmp_path / "active"))
    monkeypatch.setenv("QUOTA_DASH_MAX_AGE_S", max_age)
    spec = importlib.util.spec_from_file_location(f"qd_rf_{tmp_path.name}", _SRC)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _payload() -> dict:
    return {
        "active": "mob",
        "pause": None,
        "fleet_warnings": [],
        "accounts": [
            {
                "email": "mob@ocoron.com",
                "slugs": ["mob"],
                "five_hour": {"utilization": 40.0, "resets_at_epoch": time.time() + 7200},
                "seven_day": {"utilization": 72.0, "resets_at_epoch": time.time() + 400000},
                "source": "live",
                "age_s": None,
                "weekly_cap": None,
                "cap_walled": False,
            }
        ],
    }


def _good_page(qd, monkeypatch) -> str:
    monkeypatch.setattr(qd, "_probe", _payload)
    html = qd.generate()
    # the good page is OLDER than any later failure: back-date it a minute
    old = time.time() - 60
    os.utime(qd._HTML, (old, old))
    return html


def _break_render(qd, monkeypatch, exc: Exception) -> None:
    def boom(*_a, **_k):
        raise exc

    monkeypatch.setattr(qd, "render", boom)


def _view(qd) -> str:
    """One page view as do_GET serves it, waiting out the background regeneration it starts."""
    html = qd._fresh_html()
    worker = qd._LAST_REGEN[0]
    if worker is not None:
        worker.join(10)
    return html


def test_a_failed_regeneration_puts_a_stale_banner_on_the_served_page(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    _good_page(qd, monkeypatch)
    assert _MARKER not in _view(qd), "a healthy board carries no banner"
    _break_render(qd, monkeypatch, TypeError("render exploded"))
    _view(qd)  # this view's background regeneration fails
    served = _view(qd)  # the next view is what the reader sees
    assert _MARKER in served, "the stale page must say its last regeneration failed"
    assert "TypeError" in served
    assert re.search(r"rendered \d+ (s|min) ago", served), "the banner names the page's age"


def test_a_good_regeneration_clears_the_banner(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    _good_page(qd, monkeypatch)
    _break_render(qd, monkeypatch, TypeError("render exploded"))
    _view(qd)
    assert _MARKER in _view(qd)
    monkeypatch.undo()  # render restored ...
    qd = _load(tmp_path, monkeypatch)  # ... and a module whose env still points at tmp_path
    monkeypatch.setattr(qd, "_probe", _payload)
    qd.generate()
    assert _MARKER not in _view(qd), "a good render must take the banner away"


def test_a_good_regeneration_in_the_same_process_clears_the_banner(tmp_path, monkeypatch):
    """The same module instance: the failure record itself is cleared by the next good render."""
    qd = _load(tmp_path, monkeypatch)
    _good_page(qd, monkeypatch)
    real_render = qd.render
    _break_render(qd, monkeypatch, TypeError("render exploded"))
    _view(qd)
    assert _MARKER in _view(qd)
    monkeypatch.setattr(qd, "render", real_render)
    _view(qd)  # a good background regeneration
    assert _MARKER not in _view(qd)


def test_a_failing_synchronous_regeneration_still_serves_the_last_page(tmp_path, monkeypatch):
    """The pointer-moved branch regenerates inline; a raise there used to fail the request."""
    qd = _load(tmp_path, monkeypatch)
    good = _good_page(qd, monkeypatch)
    _break_render(qd, monkeypatch, ValueError("render exploded"))
    monkeypatch.setattr(qd, "_pointer_moved", lambda: True)
    served = qd._fresh_html()  # must not raise
    assert _MARKER in served and "ValueError" in served
    assert "Claude account quota" in served and good.split("<header>")[1][:200] in served


def test_the_banner_names_the_error_class_not_the_message(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    _good_page(qd, monkeypatch)
    secret = "token=sk-not-for-the-page /home/someone/.secret"
    _break_render(qd, monkeypatch, RuntimeError(secret))
    _view(qd)
    served = _view(qd)
    assert _MARKER in served and "RuntimeError" in served
    assert secret not in served and "sk-not-for-the-page" not in served


def test_a_page_older_than_a_probe_cycle_says_so_without_any_failure(tmp_path, monkeypatch):
    """Critique (Opus, design round): a HUNG probe or a restarted process records no failure, so a
    failure-only banner would never show. Past one probe interval plus one timeout, the page's own
    mtime is enough to say it is stale."""
    qd = _load(tmp_path, monkeypatch, max_age="100000")  # no view regenerates
    _good_page(qd, monkeypatch)
    assert _MARKER not in qd._fresh_html(), "a minute old is inside the probe cycle"
    old = time.time() - (2 * (qd.PROBE_INTERVAL_S + qd.PROBE_TIMEOUT_S) + 30)
    os.utime(qd._HTML, (old, old))
    served = qd._fresh_html()
    assert _MARKER in served and "no regeneration has finished" in served


def test_an_oserror_on_the_synchronous_path_probes_once_and_serves_the_stale_page(
    tmp_path, monkeypatch
):
    """Critique (Opus, design round): an OSError from the inline regeneration used to fall into
    _fresh_html's outer `except OSError` and run a SECOND probe for the same view."""
    qd = _load(tmp_path, monkeypatch)
    _good_page(qd, monkeypatch)
    calls = []

    def failing_locked():
        calls.append(1)
        raise OSError("disk full")

    monkeypatch.setattr(qd, "_generate_locked", failing_locked)
    monkeypatch.setattr(qd, "_pointer_moved", lambda: True)
    served = qd._fresh_html()
    assert len(calls) == 1, f"one view, one probe; got {len(calls)}"
    assert _MARKER in served and "OSError" in served


def test_a_probe_that_uses_its_full_timeout_draws_no_banner(tmp_path, monkeypatch):
    """Review round 1 (S1): a quick probe, the loop's ~interval wait, then a probe running its whole
    timeout leaves a HEALTHY page interval + timeout + render old. That must not read as stale."""
    qd = _load(tmp_path, monkeypatch, max_age="100000")
    _good_page(qd, monkeypatch)
    slow_but_healthy = qd.PROBE_INTERVAL_S + qd.PROBE_TIMEOUT_S + 15  # + render and scheduling
    old = time.time() - slow_but_healthy
    os.utime(qd._HTML, (old, old))
    assert _MARKER not in qd._fresh_html()


def test_a_page_without_the_wrap_div_gets_the_banner_inside_body(tmp_path, monkeypatch):
    """Review round 1 (S2): the fallback prepended the banner before <!DOCTYPE>."""
    qd = _load(tmp_path, monkeypatch)
    qd._LAST_RENDER_FAILURE[0] = (time.time(), "TypeError")
    page = (
        '<!DOCTYPE html><html><head><title>t</title></head><body class="x"><p>hi</p></body></html>'
    )
    served = qd._with_stale_banner(page, time.time() - 5)
    assert served.startswith("<!DOCTYPE html>"), "nothing may precede the doctype"
    body_at = served.index('<body class="x">') + len('<body class="x">')
    assert served.index(_MARKER) > body_at and served.count(_MARKER) == 1
