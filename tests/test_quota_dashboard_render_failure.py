"""W-6a0f3c65 — a regeneration that raises must not leave a fresh-looking board.

On 2026-09-07 the board froze for 16 regeneration cycles on a TypeError: the traceback went to a log
nobody reads, and the page kept saying "updated <old time> · refreshes every 20s". Since the redesign
(plan 2026-10-17-plan-1, T07) a regeneration is the probe pass alone — the views render on request —
so these tests make that pass raise and assert what a viewer is SERVED: the Accounts view's fragment,
through `_render_view` — the function `GET /v/accounts` calls — never through internal state.
"""

from __future__ import annotations

import importlib.util
import re
import time
from pathlib import Path

import pytest

from tests.quota_dashboard_isolation import (  # noqa: E402, F401
    after_load,
    isolate,
    no_network,  # noqa: E402, F401 — autouse network guard
)

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "quota_dashboard.py"
_MARKER = 'id="render-failed"'


def _load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, max_age: str = "0"):
    """A fresh module whose env-derived paths point at tmp_path (the tests/test_quota_dashboard.py
    pattern). MAX_AGE_S=0 makes every view past the floor, so each view regenerates."""
    monkeypatch.setenv("QUOTA_DASH_OUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("QUOTA_DASH_POINTER", str(tmp_path / "active"))
    monkeypatch.setenv("QUOTA_DASH_MAX_AGE_S", max_age)
    isolate(tmp_path, monkeypatch)  # tests/quota_dashboard_isolation.py
    spec = importlib.util.spec_from_file_location(f"qd_rf_{tmp_path.name}", _SRC)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    after_load(mod, monkeypatch)
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


def _good_board(qd, monkeypatch, age_s: float = 60.0) -> None:
    """One good pass, its reading back-dated ``age_s`` — OLDER than any later failure."""
    monkeypatch.setattr(qd, "_probe", _payload)
    qd.generate()
    ts, payload = qd._LAST_STATUS[0]
    qd._set_last_status(ts - age_s, payload)


def _break_pass(qd, monkeypatch, exc: Exception) -> None:
    def boom():
        raise exc

    monkeypatch.setattr(qd, "_generate_locked", boom)


def _view(qd) -> str:
    """One Accounts view as `GET /v/accounts` serves it, waiting out the regeneration it starts."""
    html = qd._render_view("accounts")
    worker = qd._LAST_REGEN[0]
    if worker is not None:
        worker.join(10)
    return html


def test_a_failed_regeneration_puts_a_stale_banner_on_the_served_view(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    _good_board(qd, monkeypatch)
    assert _MARKER not in _view(qd), "a healthy board carries no banner"
    _break_pass(qd, monkeypatch, TypeError("render exploded"))
    _view(qd)  # this view's background regeneration fails
    served = _view(qd)  # the next view is what the reader sees
    assert _MARKER in served, "the stale view must say its last regeneration failed"
    assert "TypeError" in served
    assert re.search(r"rendered \d+ (s|min) ago", served), "the banner names the reading's age"
    assert "mob@ocoron.com" in served, "the last good reading stays on the board"


def test_a_good_regeneration_clears_the_banner(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    _good_board(qd, monkeypatch)
    _break_pass(qd, monkeypatch, TypeError("render exploded"))
    _view(qd)
    assert _MARKER in _view(qd)
    monkeypatch.undo()  # the pass restored ...
    qd = _load(tmp_path, monkeypatch)  # ... and a module whose env still points at tmp_path
    monkeypatch.setattr(qd, "_probe", _payload)
    qd.generate()
    assert _MARKER not in _view(qd), "a good pass must take the banner away"


def test_a_good_regeneration_in_the_same_process_clears_the_banner(tmp_path, monkeypatch):
    """The same module instance: the failure record itself is cleared by the next good pass."""
    qd = _load(tmp_path, monkeypatch)
    _good_board(qd, monkeypatch)
    real_pass = qd._generate_locked
    _break_pass(qd, monkeypatch, TypeError("render exploded"))
    _view(qd)
    assert _MARKER in _view(qd)
    monkeypatch.setattr(qd, "_generate_locked", real_pass)
    _view(qd)  # a good background regeneration
    assert _MARKER not in _view(qd)


def test_a_failing_pointer_moved_regeneration_still_serves_the_last_reading(tmp_path, monkeypatch):
    """The pointer-moved branch regenerates in the background; a raise there must not fail the
    request, and the next view names it."""
    qd = _load(tmp_path, monkeypatch, max_age="100000")
    _good_board(qd, monkeypatch)
    _break_pass(qd, monkeypatch, ValueError("render exploded"))
    monkeypatch.setattr(qd, "_pointer_moved", lambda: True)
    _view(qd)  # must not raise; it starts the regeneration and waits it out
    served = qd._render_view("accounts")
    assert _MARKER in served and "ValueError" in served
    assert "mob@ocoron.com" in served and 'data-view-root="accounts"' in served


def test_the_banner_names_the_error_class_not_the_message(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    _good_board(qd, monkeypatch)
    secret = "token=sk-not-for-the-page /home/someone/.secret"
    _break_pass(qd, monkeypatch, RuntimeError(secret))
    _view(qd)
    served = _view(qd)
    assert _MARKER in served and "RuntimeError" in served
    assert secret not in served and "sk-not-for-the-page" not in served


def test_a_reading_older_than_a_probe_cycle_says_so_without_any_failure(tmp_path, monkeypatch):
    """Critique (Opus, design round): a HUNG probe or a restarted process records no failure, so a
    failure-only banner would never show. Past one probe interval plus one timeout, the reading's
    own age is enough to say it is stale."""
    qd = _load(tmp_path, monkeypatch, max_age="100000")  # no view regenerates
    _good_board(qd, monkeypatch)
    assert _MARKER not in qd._render_view("accounts"), "a minute old is inside the probe cycle"
    ts, payload = qd._LAST_STATUS[0]
    qd._set_last_status(time.time() - (qd.PROBE_INTERVAL_S + qd.PROBE_TIMEOUT_S + 60 + 10), payload)
    served = qd._render_view("accounts")
    assert _MARKER in served and "no probe has finished since" in served


def test_an_oserror_on_the_pointer_moved_path_probes_once_and_serves_the_stale_reading(
    tmp_path, monkeypatch
):
    """Critique (Opus, design round): an OSError from the inline regeneration used to fall into an
    outer `except OSError` and run a SECOND probe for the same view."""
    qd = _load(tmp_path, monkeypatch, max_age="100000")
    _good_board(qd, monkeypatch)
    calls = []

    def failing_locked():
        calls.append(1)
        raise OSError("disk full")

    monkeypatch.setattr(qd, "_generate_locked", failing_locked)
    monkeypatch.setattr(qd, "_pointer_moved", lambda: True)
    _view(qd)
    served = _view(qd)
    assert len(calls) == 1, f"one view, one probe; got {len(calls)}"
    assert _MARKER in served and "OSError" in served


def test_a_probe_that_uses_its_full_timeout_draws_no_banner(tmp_path, monkeypatch):
    """Review round 1 (S1): a quick probe, the loop's ~interval wait, then a probe running its whole
    timeout leaves a HEALTHY reading interval + timeout + render old. That must not read as stale."""
    qd = _load(tmp_path, monkeypatch, max_age="100000")
    _good_board(qd, monkeypatch, age_s=qd.PROBE_INTERVAL_S + qd.PROBE_TIMEOUT_S + 15)
    assert _MARKER not in qd._render_view("accounts")


def test_the_banner_sits_once_inside_the_view_root_before_the_view(tmp_path, monkeypatch):
    """Review rounds 1-2 (S2, S3/H1) pinned where a page-level banner was INJECTED (never before the
    doctype, after the real `<body>`). The redesign retired the injection: the banner is a component
    the server places first inside the quota view's root, so there is no page to splice into."""
    qd = _load(tmp_path, monkeypatch, max_age="100000")
    _good_board(qd, monkeypatch)
    qd._LAST_PROBE_FAILURE[0] = (time.time(), "TypeError")
    served = qd._render_view("accounts")
    assert served.count(_MARKER) == 1
    root_end = served.index(">") + 1
    assert served.startswith("<section") and 'data-view-root="accounts"' in served[:root_end]
    assert served.index(_MARKER) < served.index('aria-labelledby="accounts-table"')
    assert _MARKER not in qd._render_view("usage"), "a non-quota view carries no quota banner"
