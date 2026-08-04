import pathlib
import warnings

import pytest

from app import settings, worker

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_new_key_wins():
    conf = settings.load({"POLL_INTERVAL_SECONDS": "7"})
    assert conf["poll_interval_seconds"] == 7


def test_old_key_fallback_warns():
    with pytest.warns(DeprecationWarning):
        conf = settings.load({"POLL_SECS": "9"})
    assert conf["poll_interval_seconds"] == 9


def test_new_key_beats_old():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        conf = settings.load({"POLL_INTERVAL_SECONDS": "5", "POLL_SECS": "9"})
    assert conf["poll_interval_seconds"] == 5


def test_worker_exposes_poll_interval():
    w = worker.Worker({"POLL_INTERVAL_SECONDS": "11"})
    assert w.poll_interval == 11


def test_compose_uses_new_name():
    text = (ROOT / "compose.yaml").read_text()
    assert "POLL_INTERVAL_SECONDS" in text
    assert "POLL_SECS=" not in text
