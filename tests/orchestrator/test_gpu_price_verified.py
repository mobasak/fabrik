"""The GPU price table carries its verified date, and the point of use shows it (mail 01M3482Z).

The date is compared against an injected `today`, never the wall clock, so no test here turns
red on a calendar day.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from fabrik.orchestrator import gpu_rent, gpu_state


def test_the_table_age_is_measured_from_its_verified_date():
    verified = gpu_rent.PRICES_VERIFIED
    assert gpu_rent.prices_age_days(today=verified) == 0
    assert gpu_rent.prices_age_days(today=verified + timedelta(days=91)) == 91


@pytest.mark.parametrize(("age", "stale"), [(90, False), (91, True)])
def test_staleness_starts_after_the_window(age, stale):
    today = gpu_rent.PRICES_VERIFIED + timedelta(days=age)
    assert gpu_rent.prices_are_stale(today=today) is stale


def test_compare_prints_the_verified_date(monkeypatch):
    from fabrik.cli import cli

    monkeypatch.setattr(gpu_rent, "_today", lambda: gpu_rent.PRICES_VERIFIED + timedelta(days=3))
    out = CliRunner().invoke(cli, ["gpu", "compare", "pod-h100"]).output
    assert f"prices verified {gpu_rent.PRICES_VERIFIED.isoformat()} (3 days ago)" in out
    assert "STALE" not in out


def test_compare_flags_a_stale_table(monkeypatch):
    from fabrik.cli import cli

    monkeypatch.setattr(gpu_rent, "_today", lambda: gpu_rent.PRICES_VERIFIED + timedelta(days=200))
    out = CliRunner().invoke(cli, ["gpu", "compare", "pod-h100"]).output
    assert "STALE" in out and "(200 days ago)" in out


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(gpu_state, "STATE_FILE", tmp_path / "gpu-rent-state.json")
    monkeypatch.setattr(gpu_rent, "GPU_RENT_LOG", tmp_path / "gpu-rent-history.jsonl")
    from fabrik.ai import tracker as tracker_mod

    original_init = tracker_mod.UsageTracker.__init__
    monkeypatch.setattr(
        tracker_mod.UsageTracker,
        "__init__",
        lambda self, database_path=None: original_init(
            self, database_path or str(tmp_path / "u.db")
        ),
    )
    monkeypatch.delenv("MAX_DAILY_GPU_COST", raising=False)
    client = MagicMock()
    client.create_pod.return_value = {"id": "p"}
    client.wait_for_running.return_value = {"id": "p"}
    return client


def _stale_lines(caplog):
    return [r for r in caplog.records if "price table" in r.getMessage()]


def test_every_rental_warns_while_the_table_is_stale(isolated, monkeypatch, caplog):
    """Per rental, not once per process: a long-lived caller must keep hearing it."""
    monkeypatch.setattr(gpu_rent, "_today", lambda: gpu_rent.PRICES_VERIFIED + timedelta(days=120))
    with caplog.at_level(logging.WARNING, logger="fabrik.orchestrator.gpu_rent"):
        gpu_rent.rent("pod-rtx-4090", workload="t", client=isolated)
        with gpu_rent.rented("pod-rtx-4090", workload="t", client=isolated):
            pass
    assert len(_stale_lines(caplog)) == 2


def test_a_rental_on_a_fresh_table_does_not_warn(isolated, monkeypatch, caplog):
    monkeypatch.setattr(gpu_rent, "_today", lambda: gpu_rent.PRICES_VERIFIED + timedelta(days=1))
    with caplog.at_level(logging.WARNING, logger="fabrik.orchestrator.gpu_rent"):
        gpu_rent.rent("pod-rtx-4090", workload="t", client=isolated)
    assert _stale_lines(caplog) == []


def test_the_verified_date_is_a_date():
    """The watcher compares dates; a string here would make every comparison raise."""
    assert isinstance(gpu_rent.PRICES_VERIFIED, date)


def test_a_verified_date_ahead_of_today_reads_as_zero_days():
    """The constant is a local calendar date and today is UTC; never print a negative age."""
    assert gpu_rent.prices_age_days(today=gpu_rent.PRICES_VERIFIED - timedelta(days=1)) == 0


def test_a_kind_a_provider_cannot_rent_is_not_offered_by_it():
    """Modal has no H100 NVL mapping, so compare must not recommend a Modal rental that would fail."""
    advice = gpu_rent.selection_advice("pod-h100-nvl", hours=1)
    assert advice["providers"]["modal"]["supported"] is False
    with pytest.raises(NotImplementedError):
        gpu_rent.estimate_cost("pod-h100-nvl", 1, provider="modal")
