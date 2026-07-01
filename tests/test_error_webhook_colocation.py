"""Phase 2 (deploy-readiness): cross-host error_webhook guard.

GlitchTip is pinned to vps1 and the `fabrik` net is a per-host bridge, so a
watchdog on vps2/vps3 can't receive GlitchTip's POST to `<id>-watchdog:8889`.
The orchestrator must fail CLOSED at apply for `error_webhook` + non-vps1 rather
than ship a silently-dead alerting path — while leaving HTTP-based sources
(`emitter`/`health`) and vps1 deploys untouched.
"""

from __future__ import annotations

import pytest

from fabrik.orchestrator import _assert_error_webhook_colocated
from fabrik.orchestrator.exceptions import ValidationError


def _spec(sources: list[str]) -> dict:
    return {"watchdog": {"trigger_sources": sources}}


def test_error_webhook_off_hub_is_rejected():
    for host in ("vps2", "vps3"):
        with pytest.raises(ValidationError, match="error_webhook"):
            _assert_error_webhook_colocated(_spec(["health", "error_webhook"]), host)


def test_error_webhook_on_vps1_is_allowed():
    _assert_error_webhook_colocated(_spec(["error_webhook"]), "vps1")  # must not raise


def test_non_error_webhook_sources_off_hub_are_allowed():
    # emitter/health are HTTP/poll-based — no same-host :8889 ingest needed.
    _assert_error_webhook_colocated(_spec(["emitter", "health"]), "vps2")
    _assert_error_webhook_colocated(_spec([]), "vps3")


def test_specs_without_watchdog_are_allowed():
    _assert_error_webhook_colocated({}, "vps2")
    _assert_error_webhook_colocated({"watchdog": {}}, "vps3")
    _assert_error_webhook_colocated({"watchdog": None}, "vps2")
