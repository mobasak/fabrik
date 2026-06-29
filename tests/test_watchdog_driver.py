"""Tests for the watchdog sidecar driver (src/fabrik/drivers/watchdog.py).

Enables dry-run + render-context testing with no VPS/SSH, and guards the
SIDECAR_SOURCE vendor path — regression for the 2026-06-29 break where
fabrik-lib renamed `sidecar/` → `watchdog_sidecar/`, which silently aborted
`fabrik apply` for every watchdog project at the build step.
"""

from __future__ import annotations

import types

import pytest

from fabrik.drivers.watchdog import (
    SIDECAR_SOURCE,
    WatchdogDriver,
    WatchdogProvisionError,
)


def _ctx(spec: dict, *, target_vps: str | None = None) -> types.SimpleNamespace:
    return types.SimpleNamespace(spec=spec, app_name=spec.get("id"), target_vps=target_vps)


class TestSidecarSource:
    def test_points_at_watchdog_sidecar(self):
        assert SIDECAR_SOURCE.name == "watchdog_sidecar"

    def test_vendor_path_exists_on_hub(self):
        # /opt/fabrik-lib is present on the hub; a drifted path would abort
        # _build_image() at runtime, so guard it here.
        assert SIDECAR_SOURCE.is_dir(), f"sidecar vendor path missing: {SIDECAR_SOURCE}"


class TestDryRun:
    def test_dry_run_returns_image_tag_without_ssh(self):
        r = WatchdogDriver().provision(
            _ctx({"id": "demo-proj", "watchdog": {"enabled": True}}), dry_run=True
        )
        assert r["status"] == "dry-run"
        assert r["image_tag"] == "fabrik/watchdog:demo-proj"

    def test_disabled_spec_skips(self):
        r = WatchdogDriver().provision(
            _ctx({"id": "demo", "watchdog": {"enabled": False}}), dry_run=True
        )
        assert r["status"] == "skipped"

    def test_missing_id_raises(self):
        with pytest.raises(WatchdogProvisionError, match="id/name"):
            WatchdogDriver().provision(_ctx({"watchdog": {"enabled": True}}), dry_run=True)


class TestRenderContext:
    def test_defaults(self):
        rctx = WatchdogDriver()._build_render_context(
            {"id": "demo", "watchdog": {"enabled": True}}, _ctx({"id": "demo"})
        )
        assert rctx is not None
        assert rctx.project_id == "demo"
        assert rctx.image_tag == "fabrik/watchdog:demo"
        assert rctx.target_vps == "vps1"
        assert rctx.redis_url.endswith("/15")  # watchdog's dedicated Redis DB index

    def test_target_vps_from_ctx(self):
        rctx = WatchdogDriver()._build_render_context(
            {"id": "demo", "watchdog": {"enabled": True}}, _ctx({"id": "demo"}, target_vps="vps2")
        )
        assert rctx.target_vps == "vps2"
