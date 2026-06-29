"""Tests for the GlitchTip webhook drift-check (scripts/probes/glitchtip_webhook_capture.py).

Covers the pure field-map logic that mirrors the fabrik-lib watchdog parser, so a
change to GlitchTip's envelope (or to the parser's expectations) is caught.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent / "scripts" / "probes" / "glitchtip_webhook_capture.py"


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("gt_capture_under_test", TOOL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ENVELOPE = {
    "attachments": [
        {
            "title": "ZeroDivisionError: division by zero",
            "title_link": "https://errors.vps1.ocoron.com/ocoron/p/issues/2",
            "color": "#e52b50",
        }
    ]
}
ISSUE = {"issue": {"title": "DB down", "level": "fatal"}}


class TestFieldMaps:
    def test_envelope_resolves(self, mod):
        f = mod._envelope_fields(ENVELOPE)
        assert f and f["name"].startswith("ZeroDivisionError")
        assert f["url"].endswith("/issues/2")

    def test_issue_fallback_resolves(self, mod):
        assert mod._issue_fields(ISSUE)["name"] == "DB down"

    def test_envelope_none_on_empty(self, mod):
        assert mod._envelope_fields({"attachments": []}) is None
        assert mod._envelope_fields({"attachments": [{}]}) is None
        assert mod._issue_fields({"foo": "bar"}) is None


class TestVerify:
    def _fixture(self, tmp_path, body):
        p = tmp_path / "fx.json"
        p.write_text(json.dumps({"body": body}), encoding="utf-8")
        return p

    def test_verify_ok_on_envelope(self, mod, tmp_path):
        p = self._fixture(tmp_path, ENVELOPE)
        assert mod.cmd_verify(argparse.Namespace(fixture=str(p), check=True)) == 0

    def test_verify_ok_on_issue(self, mod, tmp_path):
        p = self._fixture(tmp_path, ISSUE)
        assert mod.cmd_verify(argparse.Namespace(fixture=str(p), check=True)) == 0

    def test_verify_drift_check_mode_nonzero(self, mod, tmp_path):
        p = self._fixture(tmp_path, {"unexpected": "shape"})
        assert mod.cmd_verify(argparse.Namespace(fixture=str(p), check=True)) == 1

    def test_verify_drift_warn_only_is_zero(self, mod, tmp_path):
        p = self._fixture(tmp_path, {"unexpected": "shape"})
        assert mod.cmd_verify(argparse.Namespace(fixture=str(p), check=False)) == 0

    def test_missing_fixture_warn_only_zero(self, mod, tmp_path):
        missing = str(tmp_path / "nope.json")
        assert mod.cmd_verify(argparse.Namespace(fixture=missing, check=False)) == 0
        assert mod.cmd_verify(argparse.Namespace(fixture=missing, check=True)) == 1
