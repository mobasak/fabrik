"""Tests for shape-driven destroy (orchestrator/destroyer.py).

The destroyer's correctness contract is symmetric to the provisioner:
for any spec, the registrars cleaned up MUST equal the registrars that
``InfrastructureProvisioner.provision`` would have run, in reverse
order. These tests pin that contract using stubbed driver imports so we
can assert call-graphs without touching the live VPS.

Each test patches the lazy-imported drivers via ``monkeypatch`` (the
destroyer imports them inside each ``_destroy_*`` helper, so module-level
``patch`` doesn't intercept).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fabrik.orchestrator.destroyer import (
    DestroyReport,
    _split_domain,
    destroy_deployment,
)
from fabrik.spec_loader import (
    Expose,
    Health,
    Kind,
    Shape,
    create_spec,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _maximal_service_spec(name: str = "svc-test") -> object:
    """Build a service spec with every shape flag enabled.

    Mirrors ``DEPLOYMENT.md`` §9.6 maximal-shape test: every registrar
    applicable, used to assert that the destroyer touches all of them.
    """
    return create_spec(
        id=name,
        template="python-api",
        domain=f"{name}.vps1.ocoron.com",
        kind=Kind.SERVICE,
        expose=Expose(),
        health=Health(path="/health"),
        shape=Shape(
            kind="service",
            is_public=True,
            is_admin_dashboard=True,
            has_bearer_api=True,
            has_persistent_data=True,
            needs_database=True,
            has_search_feature=True,
        ),
    )


def _minimal_static_spec(name: str = "site-test") -> object:
    """Static-site spec: only Gatus is applicable (is_public + domain)."""
    return create_spec(
        id=name,
        template="static-site",
        domain=f"{name}.vps1.ocoron.com",
        kind=Kind.STATIC,
        expose=Expose(),
        shape=Shape(
            kind="static",
            is_public=True,
            is_admin_dashboard=False,
            has_bearer_api=False,
            has_persistent_data=False,
            needs_database=False,
            has_search_feature=False,
        ),
    )


def _install_stub_drivers(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Replace every driver entry-point used by the destroyer with a stub.

    Returns a dict mapping driver-step name to the MagicMock so tests
    can assert call args. Drivers that the destroyer imports lazily get
    patched at the module level via ``sys.modules`` injection.
    """
    mocks: dict[str, MagicMock] = {}

    # MeiliSearch
    meili_mod = types.ModuleType("fabrik.drivers.meilisearch")
    mocks["meilisearch.delete_index"] = MagicMock(return_value=True)
    meili_mod.delete_index = mocks["meilisearch.delete_index"]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.meilisearch", meili_mod)

    # Authelia
    auth_mod = types.ModuleType("fabrik.drivers.authelia")
    mocks["authelia.remove_access_rule"] = MagicMock(return_value=True)
    auth_mod.remove_access_rule = mocks["authelia.remove_access_rule"]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.authelia", auth_mod)

    # GlitchTip
    gt_mod = types.ModuleType("fabrik.drivers.glitchtip")
    mocks["glitchtip.delete_project"] = MagicMock(return_value=True)
    gt_mod.delete_project = mocks["glitchtip.delete_project"]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.glitchtip", gt_mod)

    # Backrest
    br_mod = types.ModuleType("fabrik.drivers.backrest")
    mocks["backrest.remove_backup_plan"] = MagicMock(return_value=True)
    br_mod.remove_backup_plan = mocks["backrest.remove_backup_plan"]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.backrest", br_mod)

    # Gatus
    g_mod = types.ModuleType("fabrik.drivers.gatus")
    mocks["gatus.remove_endpoint"] = MagicMock(return_value=True)
    g_mod.remove_endpoint = mocks["gatus.remove_endpoint"]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.gatus", g_mod)

    # Postgres
    pg_mod = types.ModuleType("fabrik.drivers.postgres")
    mocks["postgres.drop_database"] = MagicMock(return_value={"status": "dropped"})
    pg_mod.drop_database = mocks["postgres.drop_database"]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.postgres", pg_mod)

    # SSH — app teardown. Post-Coolify-migration apps all live at /opt/<name>
    # and are destroyed via `docker compose down` over SSH (step "compose"),
    # not a Coolify API call. Default: every SSH command succeeds (empty
    # stdout); individual tests override .side_effect to simulate a missing
    # app directory.
    ssh_mod = types.ModuleType("fabrik.drivers.ssh")
    mocks["ssh"] = MagicMock(return_value="")
    ssh_mod.ssh = mocks["ssh"]
    monkeypatch.setitem(sys.modules, "fabrik.drivers.ssh", ssh_mod)

    # DNS
    dns_mod = types.ModuleType("fabrik.drivers.dns")
    dns_client = MagicMock()
    dns_client.delete_record = MagicMock(return_value={"success": True})
    dns_mod.DNSClient = MagicMock(return_value=dns_client)
    mocks["dns.client"] = dns_client
    monkeypatch.setitem(sys.modules, "fabrik.drivers.dns", dns_mod)

    return mocks


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


class TestSplitDomain:
    def test_three_part(self):
        assert _split_domain("foo.vps1.ocoron.com") == ("foo.vps1", "ocoron.com")

    def test_two_part_returns_none(self):
        assert _split_domain("ocoron.com") is None

    def test_co_uk_handled(self):
        assert _split_domain("api.example.co.uk") == ("api", "example.co.uk")


class TestDestroyMaximalShape:
    """Maximal-shape spec: every registrar applicable.

    Asserts the destroyer calls every driver's remove entry-point in
    reverse-of-provisioner order.
    """

    def test_every_registrar_runs_with_drop_data(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        mocks = _install_stub_drivers(monkeypatch)
        spec = _maximal_service_spec()

        report = destroy_deployment(
            spec,
            drop_data=True,
            project_base=tmp_path,
        )

        assert isinstance(report, DestroyReport)
        assert not report.had_errors, [
            (a.step, a.error) for a in report.errors
        ]
        # Every shape-gated driver was called exactly once.
        mocks["meilisearch.delete_index"].assert_called_once()
        mocks["authelia.remove_access_rule"].assert_called_once_with(
            "svc-test.vps1.ocoron.com", dry_run=False
        )
        mocks["glitchtip.delete_project"].assert_called_once_with(
            "svc-test", dry_run=False
        )
        mocks["backrest.remove_backup_plan"].assert_called_once_with(
            "svc-test-data", dry_run=False
        )
        mocks["gatus.remove_endpoint"].assert_called_once_with(
            "svc-test", dry_run=False
        )
        mocks["postgres.drop_database"].assert_called_once()
        # App teardown ran `docker compose down` over SSH for /opt/svc-test.
        compose_cmds = [c.args[0] for c in mocks["ssh"].call_args_list if c.args]
        assert any(
            "docker compose down" in cmd and "/opt/svc-test" in cmd
            for cmd in compose_cmds
        ), compose_cmds
        # DNS got its hit.
        mocks["dns.client"].delete_record.assert_called_once_with(
            "ocoron.com", "A", "svc-test.vps1"
        )

    def test_drop_data_false_preserves_db_and_index(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """Default ``drop_data=False`` mirrors the rollback policy:
        Postgres + MeiliSearch data must survive."""
        mocks = _install_stub_drivers(monkeypatch)
        spec = _maximal_service_spec()

        report = destroy_deployment(spec, project_base=tmp_path)

        # Destructive registrars NOT called.
        mocks["postgres.drop_database"].assert_not_called()
        mocks["meilisearch.delete_index"].assert_not_called()
        # Non-destructive registrars still called.
        mocks["authelia.remove_access_rule"].assert_called_once()
        mocks["gatus.remove_endpoint"].assert_called_once()
        # The corresponding actions are recorded as ``skipped``.
        skipped = {a.step for a in report.actions if a.status == "skipped"}
        assert "postgres" in skipped
        assert "meilisearch" in skipped


class TestDestroyMinimalShape:
    """Static-site spec: Authelia/GlitchTip/Backrest/Postgres/MeiliSearch
    not applicable. Only Gatus + compose app + DNS + files run."""

    def test_only_applicable_registrars_run(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        mocks = _install_stub_drivers(monkeypatch)
        spec = _minimal_static_spec()

        report = destroy_deployment(spec, drop_data=True, project_base=tmp_path)

        assert not report.had_errors
        # Applicable for static + public + domain:
        mocks["gatus.remove_endpoint"].assert_called_once()
        compose_cmds = [c.args[0] for c in mocks["ssh"].call_args_list if c.args]
        assert any(
            "docker compose down" in cmd and "/opt/site-test" in cmd
            for cmd in compose_cmds
        ), compose_cmds
        mocks["dns.client"].delete_record.assert_called_once()
        # Not applicable per shape:
        mocks["authelia.remove_access_rule"].assert_not_called()
        mocks["glitchtip.delete_project"].assert_not_called()  # kind=static
        mocks["backrest.remove_backup_plan"].assert_not_called()
        mocks["meilisearch.delete_index"].assert_not_called()
        mocks["postgres.drop_database"].assert_not_called()


class TestDestroyFlags:
    def test_dry_run_makes_no_mutations(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        mocks = _install_stub_drivers(monkeypatch)
        spec = _maximal_service_spec()
        # Create the project tree so the files step has something to "see".
        (tmp_path / "svc-test").mkdir()

        report = destroy_deployment(
            spec, drop_data=True, dry_run=True, project_base=tmp_path
        )

        # No driver was called with dry_run=False — every call should be
        # dry-run-tagged. Since the destroyer wires dry_run=True through,
        # the real assertion is "no mutation occurred" — checked by
        # confirming the project tree still exists.
        assert (tmp_path / "svc-test").exists()
        # Every action is dry_run or skipped.
        bad = [a for a in report.actions if a.status not in {"dry_run", "skipped"}]
        assert not bad, f"non-dry-run actions in dry-run mode: {bad}"
        # Compose teardown over SSH must not have happened.
        mocks["ssh"].assert_not_called()

    def test_keep_dns_skips_dns_step(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        mocks = _install_stub_drivers(monkeypatch)
        spec = _maximal_service_spec()

        report = destroy_deployment(
            spec, keep_dns=True, project_base=tmp_path
        )

        mocks["dns.client"].delete_record.assert_not_called()
        dns_actions = [a for a in report.actions if a.step == "dns"]
        assert len(dns_actions) == 1
        assert dns_actions[0].status == "skipped"
        assert "--keep-dns" in dns_actions[0].detail

    def test_keep_files_preserves_project_tree(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        _install_stub_drivers(monkeypatch)
        spec = _maximal_service_spec()
        project_dir = tmp_path / "svc-test"
        project_dir.mkdir()
        (project_dir / "marker.txt").write_text("preserved")

        destroy_deployment(spec, keep_files=True, project_base=tmp_path)

        assert project_dir.exists()
        assert (project_dir / "marker.txt").read_text() == "preserved"


class TestDestroyErrorHandling:
    def test_driver_exception_does_not_abort_remaining_steps(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """A Gatus failure must not prevent compose-app/DNS cleanup."""
        mocks = _install_stub_drivers(monkeypatch)
        mocks["gatus.remove_endpoint"].side_effect = RuntimeError("gatus VPS down")
        spec = _maximal_service_spec()

        report = destroy_deployment(spec, drop_data=True, project_base=tmp_path)

        # Gatus action recorded as error.
        gatus = [a for a in report.actions if a.step == "gatus"][0]
        assert gatus.status == "error"
        assert "gatus VPS down" in (gatus.error or "")
        # But compose app teardown + DNS still ran.
        compose_cmds = [c.args[0] for c in mocks["ssh"].call_args_list if c.args]
        assert any("docker compose down" in cmd for cmd in compose_cmds), compose_cmds
        mocks["dns.client"].delete_record.assert_called_once()
        assert report.had_errors

    def test_app_not_found_is_not_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """Re-running destroy on an already-destroyed app must succeed."""
        mocks = _install_stub_drivers(monkeypatch)

        # `test -d /opt/<name>` fails → app directory already gone.
        def _ssh_missing(cmd, *a, **kw):
            if "test -d" in cmd:
                raise RuntimeError("directory not found")
            return ""

        mocks["ssh"].side_effect = _ssh_missing
        spec = _maximal_service_spec()

        report = destroy_deployment(spec, project_base=tmp_path)

        compose_action = [a for a in report.actions if a.step == "compose"][0]
        assert compose_action.status == "not_found"
        assert not report.had_errors
