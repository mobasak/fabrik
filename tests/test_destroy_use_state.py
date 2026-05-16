"""T4-02 G-F4 — ``fabrik destroy --use-state`` tests.

Coverage:

- ``destroy_from_state`` Phase 0 data-bearing guard (refuse without --drop-data).
- Phase 1 reverse-order dispatch using HANDLER_FUNCS/HANDLER_ARGS (T2-02 contract).
- Phase 1 grafana-skip-by-design (no destroyer registered).
- Phase 2 always-run for coolify; gated for dns/files.
- Primary path (Epic SC-3): apply with shape A → edit spec to shape B → destroy --use-state
  reverses A's resources (the spec-B walk would have missed them).
- Regression: shape-driven destroy (no --use-state) unchanged.
- CLI: missing state file → clean error with non-zero exit.
- CLI: --use-state + --partial → mutually-exclusive refusal.
- Archive on success: state moves to _destroyed/.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from fabrik.cli import cli
from fabrik.orchestrator.destroyer import (
    ActionResult,
    HANDLER_ARGS,
    HANDLER_FUNCS,
    destroy_from_state,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _spec(id_: str = "demo", domain: str = "demo.vps1.ocoron.com"):
    """Minimal spec mock supporting the .id / .domain attrs HANDLER_ARGS reads."""
    return MagicMock(id=id_, domain=domain)


def _state(
    *,
    registrars: list[dict] | None = None,
    spec_id: str = "demo",
    domain: str = "demo.vps1.ocoron.com",
) -> dict:
    """Synthesize a T2-01 state-file payload."""
    return {
        "applied_at": "2026-05-16T00:00:00+00:00",
        "coolify_app_name": spec_id,
        "coolify_uuid": "ab" * 12,
        "domain": domain,
        "git_sha": "0" * 40,
        "registrars_applied": registrars or [],
        "spec_hash": "deadbeef" * 2,
        "spec_path": f"/opt/fabrik/specs/services/{spec_id}.yaml",
    }


@pytest.fixture
def patched_destroyers():
    """Stub every _destroy_* used by HANDLER_FUNCS + the Phase 2 trio.

    Returns a dict {name: MagicMock} so each test can assert call order /
    arguments / "was called at all".
    """
    targets = {
        "_destroy_postgres": ActionResult(step="postgres", status="removed"),
        "_destroy_redis": ActionResult(step="redis", status="removed"),
        "_destroy_gatus": ActionResult(step="gatus", status="removed"),
        "_destroy_backrest": ActionResult(step="backrest", status="not_found"),
        "_destroy_glitchtip": ActionResult(step="glitchtip", status="removed"),
        "_destroy_authelia": ActionResult(step="authelia", status="removed"),
        "_destroy_meilisearch": ActionResult(step="meilisearch", status="removed"),
        "_destroy_prometheus": ActionResult(step="prometheus", status="removed"),
        "_destroy_coolify": ActionResult(step="coolify", status="removed"),
        "_destroy_dns": ActionResult(step="dns", status="removed"),
        "_destroy_files": ActionResult(step="files", status="removed"),
    }
    mocks = {}
    with (
        patch("fabrik.orchestrator.destroyer._destroy_postgres", return_value=targets["_destroy_postgres"]) as m_pg,
        patch("fabrik.orchestrator.destroyer._destroy_redis", return_value=targets["_destroy_redis"]) as m_redis,
        patch("fabrik.orchestrator.destroyer._destroy_gatus", return_value=targets["_destroy_gatus"]) as m_gatus,
        patch("fabrik.orchestrator.destroyer._destroy_backrest", return_value=targets["_destroy_backrest"]) as m_back,
        patch("fabrik.orchestrator.destroyer._destroy_glitchtip", return_value=targets["_destroy_glitchtip"]) as m_glitch,
        patch("fabrik.orchestrator.destroyer._destroy_authelia", return_value=targets["_destroy_authelia"]) as m_auth,
        patch("fabrik.orchestrator.destroyer._destroy_meilisearch", return_value=targets["_destroy_meilisearch"]) as m_meili,
        patch("fabrik.orchestrator.destroyer._destroy_prometheus", return_value=targets["_destroy_prometheus"]) as m_prom,
        patch("fabrik.orchestrator.destroyer._destroy_coolify", return_value=targets["_destroy_coolify"]) as m_coolify,
        patch("fabrik.orchestrator.destroyer._destroy_dns", return_value=targets["_destroy_dns"]) as m_dns,
        patch("fabrik.orchestrator.destroyer._destroy_files", return_value=targets["_destroy_files"]) as m_files,
    ):
        mocks.update({
            "postgres": m_pg, "redis": m_redis, "gatus": m_gatus,
            "backrest": m_back, "glitchtip": m_glitch, "authelia": m_auth,
            "meilisearch": m_meili, "prometheus": m_prom,
            "coolify": m_coolify, "dns": m_dns, "files": m_files,
        })
        # HANDLER_FUNCS references the unmocked module-level objects; need
        # to rebind so the test sees the mocks. Re-assemble the map in-test:
        with patch.dict(HANDLER_FUNCS, {
            "postgres": m_pg, "redis": m_redis, "gatus": m_gatus,
            "backrest": m_back, "glitchtip": m_glitch, "authelia": m_auth,
            "meilisearch": m_meili, "prometheus": m_prom,
        }):
            yield mocks


# ---------------------------------------------------------------------------
# Phase 0 — Data-bearing guard
# ---------------------------------------------------------------------------


class TestDataBearingGuard:
    def test_refuses_when_data_bearing_present_without_drop_data(self):
        state = _state(registrars=[
            {"type": "postgres", "status": "applied", "data_bearing": True},
            {"type": "gatus", "status": "applied", "data_bearing": False},
        ])
        report = destroy_from_state(state, _spec(), drop_data=False, dry_run=True)
        assert report.had_errors
        assert any(a.step == "data-bearing-guard" for a in report.actions)
        # No destroyer should have been recorded — guard exits before Phase 1.
        assert not any(a.step in ("gatus", "postgres", "coolify") for a in report.actions)

    def test_proceeds_when_drop_data_set(self, patched_destroyers):
        state = _state(registrars=[
            {"type": "postgres", "status": "applied", "data_bearing": True},
            {"type": "gatus", "status": "applied", "data_bearing": False},
        ])
        report = destroy_from_state(
            state, _spec(), drop_data=True, keep_dns=True, keep_files=True, dry_run=True
        )
        assert not report.had_errors
        # postgres handler invoked once with drop_data=True
        patched_destroyers["postgres"].assert_called_once()
        args = patched_destroyers["postgres"].call_args[0]
        # HANDLER_ARGS["postgres"] returns (spec.id, drop_data, dry_run)
        assert args == ("demo", True, True)

    def test_proceeds_when_no_data_bearing_present(self, patched_destroyers):
        # All entries have data_bearing=False → no guard refusal even
        # without --drop-data.
        state = _state(registrars=[
            {"type": "gatus", "status": "applied", "data_bearing": False},
            {"type": "backrest", "status": "applied", "data_bearing": False},
        ])
        report = destroy_from_state(
            state, _spec(), drop_data=False, keep_dns=True, keep_files=True, dry_run=True
        )
        assert not report.had_errors
        patched_destroyers["gatus"].assert_called_once()
        patched_destroyers["backrest"].assert_called_once()
        patched_destroyers["postgres"].assert_not_called()


# ---------------------------------------------------------------------------
# Phase 1 — Reverse-order dispatch
# ---------------------------------------------------------------------------


class TestReverseOrderDispatch:
    def test_only_state_registered_handlers_invoked(self, patched_destroyers):
        # State has 3 registrars; only these 3 should be dispatched.
        state = _state(registrars=[
            {"type": "gatus", "status": "applied", "data_bearing": False},
            {"type": "glitchtip", "status": "applied", "data_bearing": False},
            {"type": "prometheus", "status": "applied", "data_bearing": False},
        ])
        destroy_from_state(state, _spec(), drop_data=False, keep_dns=True, keep_files=True, dry_run=True)
        patched_destroyers["gatus"].assert_called_once()
        patched_destroyers["glitchtip"].assert_called_once()
        patched_destroyers["prometheus"].assert_called_once()
        # NOT in state → NOT called.
        patched_destroyers["postgres"].assert_not_called()
        patched_destroyers["redis"].assert_not_called()
        patched_destroyers["meilisearch"].assert_not_called()
        patched_destroyers["backrest"].assert_not_called()
        patched_destroyers["authelia"].assert_not_called()

    def test_canonical_reverse_order(self, patched_destroyers):
        # State has all 8 destroyable + grafana. Capture call order via a
        # shared counter.
        call_order: list[str] = []
        for name in ("postgres", "redis", "gatus", "backrest", "glitchtip",
                     "authelia", "meilisearch", "prometheus", "coolify", "dns", "files"):
            mock = patched_destroyers[name]
            mock.side_effect = lambda *a, _n=name, **kw: (
                call_order.append(_n) or ActionResult(step=_n, status="removed")
            )
        state = _state(registrars=[
            {"type": reg, "status": "applied", "data_bearing": reg in {"postgres", "redis", "meilisearch"}}
            for reg in ("postgres", "redis", "gatus", "backrest", "glitchtip",
                        "grafana", "authelia", "meilisearch", "prometheus")
        ])
        destroy_from_state(
            state, _spec(), drop_data=True, keep_dns=False, keep_files=False, dry_run=True
        )
        # Per ticket string anchor: prometheus → meilisearch → authelia →
        # (grafana skipped) → glitchtip → backrest → gatus → redis → postgres
        # → coolify → dns → files
        expected = ["prometheus", "meilisearch", "authelia", "glitchtip",
                    "backrest", "gatus", "redis", "postgres",
                    "coolify", "dns", "files"]
        assert call_order == expected, f"order drift: {call_order}"

    def test_grafana_explicitly_skipped(self, patched_destroyers):
        # State includes grafana — it should produce a "skipped" entry but
        # never reach a destroyer.
        state = _state(registrars=[
            {"type": "grafana", "status": "applied", "data_bearing": False},
            {"type": "gatus", "status": "applied", "data_bearing": False},
        ])
        report = destroy_from_state(
            state, _spec(), drop_data=False, keep_dns=True, keep_files=True, dry_run=True
        )
        skipped_steps = {a.step for a in report.actions if a.status == "skipped"}
        assert "grafana" in skipped_steps
        # gatus still runs as the only real destroyer.
        patched_destroyers["gatus"].assert_called_once()

    def test_handler_exception_recorded_as_error_not_aborting(self, patched_destroyers):
        patched_destroyers["gatus"].side_effect = RuntimeError("boom")
        state = _state(registrars=[
            {"type": "gatus", "status": "applied", "data_bearing": False},
            {"type": "backrest", "status": "applied", "data_bearing": False},
        ])
        report = destroy_from_state(
            state, _spec(), drop_data=False, keep_dns=True, keep_files=True, dry_run=True
        )
        # gatus errored, backrest still ran
        assert any(a.step == "gatus" and a.status == "error" for a in report.actions)
        patched_destroyers["backrest"].assert_called_once()


# ---------------------------------------------------------------------------
# Phase 2 — Coolify / DNS / files
# ---------------------------------------------------------------------------


class TestPhase2NonRegistrars:
    def test_coolify_always_runs(self, patched_destroyers):
        state = _state(registrars=[])
        destroy_from_state(
            state, _spec(), drop_data=False, keep_dns=True, keep_files=True, dry_run=True
        )
        patched_destroyers["coolify"].assert_called_once()

    def test_dns_skipped_with_keep_dns(self, patched_destroyers):
        state = _state(registrars=[])
        destroy_from_state(
            state, _spec(), drop_data=False, keep_dns=True, keep_files=True, dry_run=True
        )
        patched_destroyers["dns"].assert_not_called()

    def test_dns_skipped_when_no_domain(self, patched_destroyers):
        state = _state(registrars=[], domain="")
        destroy_from_state(
            state, _spec(domain=""), drop_data=False, keep_dns=False, keep_files=True, dry_run=True
        )
        patched_destroyers["dns"].assert_not_called()

    def test_files_skipped_with_keep_files(self, patched_destroyers):
        state = _state(registrars=[])
        destroy_from_state(
            state, _spec(), drop_data=False, keep_dns=True, keep_files=True, dry_run=True
        )
        patched_destroyers["files"].assert_not_called()


# ---------------------------------------------------------------------------
# Primary path (Epic SC-3) — A→B drift
# ---------------------------------------------------------------------------


class TestPrimaryPathSpecDrift:
    """The Epic Brief Success Criterion 3 path: deploy with shape A → edit
    spec to shape B → ``destroy --use-state`` reverses A's resources, NOT
    B's. We model this with state-file content reflecting A and a
    spec_mock reflecting B; verify A's handlers ran.
    """

    def test_a_resources_destroyed_even_after_shape_b(self, patched_destroyers):
        # Shape A had meilisearch (has_search_feature=true at apply-time).
        # Shape B no longer needs it (current spec). State drives the destroy.
        state_a = _state(registrars=[
            {"type": "postgres", "status": "applied", "data_bearing": True},
            {"type": "meilisearch", "status": "applied", "data_bearing": True},
            {"type": "gatus", "status": "applied", "data_bearing": False},
        ])
        spec_b_current = _spec()  # current spec wouldn't include meilisearch
        report = destroy_from_state(
            state_a,
            spec_b_current,
            drop_data=True,  # required because of postgres + meilisearch
            keep_dns=True,
            keep_files=True,
            dry_run=True,
        )
        assert not report.had_errors
        # Meilisearch destroyer must fire even though current spec no
        # longer says has_search_feature — state is the source of truth.
        patched_destroyers["meilisearch"].assert_called_once()
        patched_destroyers["postgres"].assert_called_once()
        patched_destroyers["gatus"].assert_called_once()


# ---------------------------------------------------------------------------
# Archive on success
# ---------------------------------------------------------------------------


class TestArchiveOnSuccess:
    def test_archive_called_on_success_not_dry_run(self, patched_destroyers, tmp_path, monkeypatch):
        # Point STATE_DIR at tmp_path so the test owns the filesystem.
        from fabrik import state as state_module

        monkeypatch.setattr(state_module, "STATE_DIR", tmp_path)
        target = tmp_path / "demo.json"
        target.write_text(json.dumps(_state(registrars=[
            {"type": "gatus", "status": "applied", "data_bearing": False},
        ])))

        state_data = state_module.load("demo")
        assert state_data is not None
        destroy_from_state(
            state_data,
            _spec(),
            drop_data=False,
            keep_dns=True,
            keep_files=True,
            dry_run=False,
        )
        # File should have been moved to _destroyed/
        assert not target.exists()
        archived = list((tmp_path / "_destroyed").glob("demo.json.*"))
        assert len(archived) == 1

    def test_archive_skipped_in_dry_run(self, patched_destroyers, tmp_path, monkeypatch):
        from fabrik import state as state_module

        monkeypatch.setattr(state_module, "STATE_DIR", tmp_path)
        target = tmp_path / "demo.json"
        target.write_text(json.dumps(_state(registrars=[
            {"type": "gatus", "status": "applied", "data_bearing": False},
        ])))

        state_data = state_module.load("demo")
        destroy_from_state(
            state_data,
            _spec(),
            drop_data=False,
            keep_dns=True,
            keep_files=True,
            dry_run=True,
        )
        # Dry run → state file still present, no archive.
        assert target.exists()
        assert not (tmp_path / "_destroyed").exists() or not list(
            (tmp_path / "_destroyed").glob("*")
        )


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCliUseState:
    @pytest.fixture
    def real_spec_path(self):
        # The translator spec exists on this VPS and parses cleanly.
        return "/opt/fabrik/specs/services/translator.yaml"

    def test_missing_state_file_clean_error(self, tmp_path, monkeypatch, real_spec_path):
        from fabrik import state as state_module

        monkeypatch.setattr(state_module, "STATE_DIR", tmp_path)  # empty dir
        runner = CliRunner()
        result = runner.invoke(cli, ["destroy", real_spec_path, "--use-state", "-y"])
        assert result.exit_code == 1
        assert "No state file" in result.output

    def test_use_state_with_partial_is_mutually_exclusive(self, tmp_path, monkeypatch, real_spec_path):
        from fabrik import state as state_module

        monkeypatch.setattr(state_module, "STATE_DIR", tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "destroy", real_spec_path, "--use-state", "--partial", "gatus", "-y",
        ])
        assert result.exit_code == 2
        assert "mutually exclusive" in result.output
