"""Behaviour tests for the box-local quota dashboard (scripts/sysadmin/quota_dashboard.py).

Three things carry real risk and are pinned here; the rest is presentation.

1. **The regeneration floor bounds probe volume.** `--status --json` makes live API probes,
   so a page that re-probed per view would turn a self-refreshing browser tab into a probe
   storm. Serving N requests inside the floor must cost exactly ONE probe.
2. **A failed probe never blanks the board.** The operator reads this to decide whether work
   can continue; an empty page on a transport blip is worse than a stale one, so the last
   good payload must survive with its failure visible.
3. **The board shows REMAINING, not used.** The CLI prints utilisation; this page inverts it,
   and an inversion bug would read as "plenty of quota" at the moment there is none.
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "quota_dashboard.py"


def _load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **env: str):
    """Import a FRESH module instance whose env-derived module constants point at tmp_path."""
    monkeypatch.setenv("QUOTA_DASH_OUT_DIR", str(tmp_path / "out"))
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location(f"qd_{tmp_path.name}", _SRC)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _payload(session: float = 40.0, weekly: float = 72.0) -> dict:
    return {
        "active": "mob",
        "pause": None,
        "fleet_warnings": [],
        "accounts": [
            {
                "email": "mob@ocoron.com",
                "slugs": ["mob"],
                "five_hour": {"utilization": session, "resets_at_epoch": time.time() + 7200},
                "seven_day": {"utilization": weekly, "resets_at_epoch": time.time() + 400000},
                "source": "live",
                "age_s": None,
                "weekly_cap": None,
                "cap_walled": False,
            }
        ],
    }


def test_serving_inside_the_floor_costs_exactly_one_probe(tmp_path, monkeypatch):
    """The probe-volume bound: many views inside QUOTA_DASH_MAX_AGE_S → ONE probe."""
    qd = _load(tmp_path, monkeypatch, QUOTA_DASH_MAX_AGE_S="600")
    calls: list[float] = []
    monkeypatch.setattr(qd, "_probe", lambda: (calls.append(time.time()), _payload())[1])

    first = qd._fresh_html()
    for _ in range(5):
        again = qd._fresh_html()

    assert len(calls) == 1, f"expected 1 probe for 6 views inside the floor, got {len(calls)}"
    assert "mob@ocoron.com" in first and "mob@ocoron.com" in again


def test_a_view_past_the_floor_reprobes(tmp_path, monkeypatch):
    """The other half of the bound: the page must not go stale forever."""
    qd = _load(tmp_path, monkeypatch, QUOTA_DASH_MAX_AGE_S="0")
    calls: list[int] = []
    monkeypatch.setattr(qd, "_probe", lambda: (calls.append(1), _payload())[1])

    qd._fresh_html()
    qd._fresh_html()

    assert len(calls) == 2


def test_probe_failure_keeps_the_last_good_board_and_says_so(tmp_path, monkeypatch):
    """Never blank: a transport failure renders the previous payload behind a banner."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", lambda: _payload(weekly=72.0))
    qd.generate()  # seeds quota.json with a good payload

    def _boom():
        raise RuntimeError("connection reset")

    monkeypatch.setattr(qd, "_probe", _boom)
    html = qd.generate()

    assert "mob@ocoron.com" in html, "the last good board must survive a failed probe"
    assert "28%" in html, "…including its numbers (100-72 weekly remaining)"
    assert "live probe failed" in html.lower()
    assert "connection reset" in html


def test_the_board_reports_remaining_not_used(tmp_path, monkeypatch):
    """Inversion guard: 91% used must render as 9% left, not 91%."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", lambda: _payload(session=0.0, weekly=91.0))

    html = qd.generate()

    assert '<span class="pct warn">9%</span> left' in html, "weekly 91% used → 9% left"
    assert '<span class="pct ok">100%</span> left' in html, "session 0% used → 100% left"
    assert "91% used" in html, "the raw utilisation stays visible as the sub-line"


def test_red_starts_where_the_fleet_abandons_the_account(tmp_path, monkeypatch):
    """The crit boundary is not cosmetic: ≤5% left == ≥95% used == the flip threshold, i.e.
    red means 'the fleet is about to leave this account', amber means 'still usable'."""
    qd = _load(tmp_path, monkeypatch)

    monkeypatch.setattr(qd, "_probe", lambda: _payload(session=0.0, weekly=95.0))
    assert '<span class="pct crit">5%</span> left' in qd.generate()

    monkeypatch.setattr(qd, "_probe", lambda: _payload(session=0.0, weekly=94.0))
    assert '<span class="pct warn">6%</span> left' in qd.generate()


def test_cap_walled_account_is_named_as_reserved(tmp_path, monkeypatch):
    """The operator's reserve must be legible on the board, not just in the CLI."""
    qd = _load(tmp_path, monkeypatch)
    payload = _payload()
    payload["accounts"][0].update(
        {"email": "ob@ocoron.com", "slugs": ["ob"], "weekly_cap": 90, "cap_walled": True}
    )
    monkeypatch.setattr(qd, "_probe", lambda: payload)

    html = qd.generate()

    assert "cap 90%" in html
    assert "RESERVED" in html and "fleet excluded" in html


def test_generate_writes_both_artifacts(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", lambda: _payload())

    qd.generate()

    assert qd._HTML.is_file() and qd._JSON.is_file()
    assert json.loads(qd._JSON.read_text())["active"] == "mob"


def test_no_credential_paths_are_read_by_the_dashboard():
    """Boundary: the view shells the rotation CLI; it must never touch credential files."""
    src = _SRC.read_text(encoding="utf-8")
    assert ".credentials.json" not in src
    assert "manager-accounts" not in src


def test_a_cached_reading_older_than_its_window_reads_unknown_not_100(tmp_path, monkeypatch):
    """The permanently-green class, caught live by the operator: an idle account's 5-hour
    reading cached 8h ago describes a window that has ROLLED OVER COMPLETELY. Rendering it as
    "100% left" can only ever reassure — it means "we have not looked", not "plenty of quota".
    The weekly cell keeps its number at that age (a 7-day window is still meaningful)."""
    qd = _load(tmp_path, monkeypatch)
    payload = _payload(session=0.0, weekly=91.0)
    payload["active"] = "someone-else"  # this row must NOT be the active pointer
    payload["accounts"][0].update({"source": "cache", "age_s": 8.5 * 3600})
    monkeypatch.setattr(qd, "_probe", lambda: payload)

    html = qd.generate()

    assert '<span class="pct ok">100%</span> left' not in html, "no unearned reassuring 100%"
    assert "idle" in html, "a non-active account's rolled window is EMPTY by construction — say so"
    assert "not the active pointer" in html, "and say why it is derivable, not measured"
    assert '<span class="pct warn">9%</span> left' in html, "the 7-day cell survives at 8.5h"


def test_a_cached_reading_younger_than_its_window_still_shows_the_number(tmp_path, monkeypatch):
    """The other half: 30 minutes into a 5-hour window the cached reading is still about the
    window we are in, so suppressing it would throw away real information."""
    qd = _load(tmp_path, monkeypatch)
    payload = _payload(session=40.0, weekly=50.0)
    payload["accounts"][0].update({"source": "cache", "age_s": 1800.0})
    monkeypatch.setattr(qd, "_probe", lambda: payload)

    html = qd.generate()

    assert '<span class="pct ok">60%</span> left' in html
    assert "which has since rolled" not in html


def test_the_active_account_cannot_claim_idle_when_its_window_rolled(tmp_path, monkeypatch):
    """The 'idle' shortcut is only sound because a non-active account cannot burn fleet quota.
    The ACTIVE account can, so a rolled-over window there is genuinely unknown, not idle."""
    qd = _load(tmp_path, monkeypatch)
    payload = _payload(session=0.0, weekly=50.0)
    payload["active"] = "mob"  # the row below IS mob
    payload["accounts"][0].update({"source": "cache", "age_s": 8.5 * 3600})
    monkeypatch.setattr(qd, "_probe", lambda: payload)

    html = qd.generate()

    assert "unknown" in html and ">idle<" not in html


def test_a_capped_account_surfaces_the_browser_blind_spot(tmp_path, monkeypatch):
    """A cap exists because the operator uses that account in the browser — usage no probe of
    ours can see. An 'idle' cell there must not imply we checked."""
    qd = _load(tmp_path, monkeypatch)
    payload = _payload(session=0.0, weekly=91.0)
    payload["active"] = "someone-else"
    payload["accounts"][0].update({"source": "cache", "age_s": 8.5 * 3600, "weekly_cap": 90})
    monkeypatch.setattr(qd, "_probe", lambda: payload)

    assert "browser use is not visible here" in qd.generate()
