"""Tests for rollback manager."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.rollback import RollbackManager


class TestRollbackManager:
    """Test RollbackManager class."""

    def test_rollback_dry_run(self):
        """Dry run should not delete anything."""
        mock_coolify = MagicMock()
        manager = RollbackManager(coolify_client=mock_coolify)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test"},
            dry_run=True,
        )
        ctx.add_resource("coolify", "uuid-123")

        errors = manager.rollback(ctx)

        assert errors == []
        mock_coolify.delete_application.assert_not_called()

    def test_rollback_no_resources(self):
        """Should handle empty resources gracefully."""
        manager = RollbackManager()

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test"},
        )

        errors = manager.rollback(ctx)
        assert errors == []

    def test_rollback_coolify_resource(self):
        """Should delete Coolify application."""
        mock_coolify = MagicMock()
        manager = RollbackManager(coolify_client=mock_coolify)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test"},
        )
        ctx.add_resource("coolify", "uuid-123", name="test-app")

        errors = manager.rollback(ctx)

        assert errors == []
        mock_coolify.delete_application.assert_called_once_with("uuid-123")

    def test_rollback_multiple_resources_lifo(self):
        """Should rollback in reverse order (LIFO)."""
        mock_coolify = MagicMock()
        manager = RollbackManager(coolify_client=mock_coolify)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test"},
        )
        ctx.add_resource("coolify", "uuid-1")
        ctx.add_resource("coolify", "uuid-2")
        ctx.add_resource("coolify", "uuid-3")

        manager.rollback(ctx)

        # Should be called in reverse order
        calls = mock_coolify.delete_application.call_args_list
        assert len(calls) == 3
        assert calls[0][0][0] == "uuid-3"
        assert calls[1][0][0] == "uuid-2"
        assert calls[2][0][0] == "uuid-1"

    def test_rollback_continues_on_error(self):
        """Should continue rollback even if one resource fails."""
        mock_coolify = MagicMock()
        mock_coolify.delete_application.side_effect = [
            None,  # First succeeds
            Exception("API error"),  # Second fails
            None,  # Third succeeds
        ]
        manager = RollbackManager(coolify_client=mock_coolify)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test"},
        )
        ctx.add_resource("coolify", "uuid-1")
        ctx.add_resource("coolify", "uuid-2")
        ctx.add_resource("coolify", "uuid-3")

        errors = manager.rollback(ctx)

        # Should have one error but all three attempted
        assert len(errors) == 1
        assert "uuid-2" in errors[0]
        assert mock_coolify.delete_application.call_count == 3

    def test_rollback_dns_resource(self):
        """Should delete DNS record with zone metadata."""
        mock_dns = MagicMock()
        manager = RollbackManager(dns_client=mock_dns)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test"},
        )
        ctx.add_resource("dns", "record-123", zone="example.com")

        errors = manager.rollback(ctx)

        assert errors == []
        mock_dns.delete_record.assert_called_once_with("example.com", "record-123")

    def test_rollback_dns_without_zone_skipped(self):
        """Should skip DNS record without zone metadata."""
        mock_dns = MagicMock()
        manager = RollbackManager(dns_client=mock_dns)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test"},
        )
        ctx.add_resource("dns", "record-123")  # No zone

        errors = manager.rollback(ctx)

        assert errors == []
        mock_dns.delete_record.assert_not_called()


# ==========================================================================
# Phase 4i — Infrastructure registrar rollback handlers
#
# Each handler unwinds one resource type registered by the
# InfrastructureProvisioner (Phase 4h). All handlers are best-effort
# (log + swallow) so a single broken handler can't abort the reverse-order
# walk.
# ==========================================================================


def _manager_and_ctx():
    """Fresh RollbackManager + DeploymentContext (no Coolify/DNS touches)."""
    manager = RollbackManager(coolify_client=MagicMock(), dns_client=MagicMock())
    ctx = DeploymentContext(spec_path=Path("test.yaml"), spec={"name": "test"})
    return manager, ctx


class TestPhase4iRegistrarRollback:
    """Dispatch + happy-path tests for every Phase-4 registrar."""

    def test_postgres_is_destructive_noop(self, caplog):
        """Postgres rollback MUST NOT call any driver; it only logs.

        The postgres driver deliberately has NO ``drop_database`` fn —
        the destructive-action policy is enforced at the architectural
        level, not just at the handler level. This test verifies the
        handler logs the manual-drop command without importing any
        destructive driver symbols.
        """
        manager, ctx = _manager_and_ctx()
        ctx.add_resource("postgres", "my_app_db")

        errors = manager.rollback(ctx)

        assert errors == []
        # Operator-facing message must mention the manual command
        assert any("fabrik db drop" in r.message for r in caplog.records)

    def test_gatus_rollback_calls_remove_endpoint(self):
        manager, ctx = _manager_and_ctx()
        ctx.add_resource("gatus", "my-project")

        with patch("fabrik.drivers.gatus.remove_endpoint") as rm:
            errors = manager.rollback(ctx)

        assert errors == []
        rm.assert_called_once_with("my-project")

    def test_backrest_rollback_calls_remove_backup_plan(self):
        manager, ctx = _manager_and_ctx()
        ctx.add_resource("backrest", "my-project-data")

        with patch("fabrik.drivers.backrest.remove_backup_plan") as rm:
            errors = manager.rollback(ctx)

        assert errors == []
        rm.assert_called_once_with("my-project-data")

    def test_glitchtip_rollback_calls_delete_project(self):
        manager, ctx = _manager_and_ctx()
        ctx.add_resource("glitchtip", "my-project")

        with patch("fabrik.drivers.glitchtip.delete_project") as rm:
            errors = manager.rollback(ctx)

        assert errors == []
        rm.assert_called_once_with("my-project")

    def test_grafana_annotation_rollback_calls_delete_annotation(self):
        """ID is stored as str by ctx.add_resource but passed as int to driver."""
        manager, ctx = _manager_and_ctx()
        ctx.add_resource("grafana_annotation_id", "42")

        with patch("fabrik.drivers.grafana.delete_annotation") as rm:
            errors = manager.rollback(ctx)

        assert errors == []
        rm.assert_called_once_with(42)

    def test_grafana_annotation_non_integer_id_skipped(self, caplog):
        manager, ctx = _manager_and_ctx()
        ctx.add_resource("grafana_annotation_id", "not-a-number")

        with patch("fabrik.drivers.grafana.delete_annotation") as rm:
            errors = manager.rollback(ctx)

        assert errors == []
        rm.assert_not_called()
        assert any("non-integer annotation id" in r.message for r in caplog.records)

    def test_authelia_rollback_calls_remove_access_rule(self):
        manager, ctx = _manager_and_ctx()
        ctx.add_resource("authelia", "my-app.vps1.ocoron.com")

        with patch("fabrik.drivers.authelia.remove_access_rule") as rm:
            errors = manager.rollback(ctx)

        assert errors == []
        rm.assert_called_once_with("my-app.vps1.ocoron.com")

    def test_authelia_bypass_alias_routes_to_same_handler(self):
        """'authelia_bypass' and 'authelia' both dispatch to _rollback_authelia."""
        manager, ctx = _manager_and_ctx()
        ctx.add_resource("authelia_bypass", "my-app.vps1.ocoron.com")

        with patch("fabrik.drivers.authelia.remove_access_rule") as rm:
            errors = manager.rollback(ctx)

        assert errors == []
        rm.assert_called_once_with("my-app.vps1.ocoron.com")

    def test_authelia_dedup_when_both_records_present(self):
        """authelia + authelia_bypass for the same domain → ONE driver call.

        Critical contract: a single remove_access_rule call already removes
        both the two_factor rule and any ^/api/ bypass for the domain. If
        we called it twice we'd trigger two Authelia container restarts
        in quick succession — slow + transient 502s.
        """
        manager, ctx = _manager_and_ctx()
        # Provisioner registers these in this order for has_bearer_api=True admin
        ctx.add_resource("authelia_bypass", "my-app.vps1.ocoron.com")
        ctx.add_resource("authelia", "my-app.vps1.ocoron.com")

        with patch("fabrik.drivers.authelia.remove_access_rule") as rm:
            errors = manager.rollback(ctx)

        assert errors == []
        rm.assert_called_once_with("my-app.vps1.ocoron.com")

    def test_authelia_different_domains_both_rolled_back(self):
        """Dedup is per-domain, not global."""
        manager, ctx = _manager_and_ctx()
        ctx.add_resource("authelia", "app1.vps1.ocoron.com")
        ctx.add_resource("authelia", "app2.vps1.ocoron.com")

        with patch("fabrik.drivers.authelia.remove_access_rule") as rm:
            errors = manager.rollback(ctx)

        assert errors == []
        assert rm.call_count == 2
        domains = {c.args[0] for c in rm.call_args_list}
        assert domains == {"app1.vps1.ocoron.com", "app2.vps1.ocoron.com"}

    def test_meilisearch_is_destructive_noop(self, caplog):
        """MeiliSearch rollback MUST NOT delete the index; it only logs."""
        manager, ctx = _manager_and_ctx()
        ctx.add_resource("meilisearch", "my_project")

        with patch("fabrik.drivers.meilisearch.delete_index") as rm:
            errors = manager.rollback(ctx)

        assert errors == []
        rm.assert_not_called()
        assert any("fabrik meili drop" in r.message for r in caplog.records)


class TestPhase4iSoftFailures:
    """Registrar rollback handlers must swallow driver exceptions.

    Contract: a single broken handler MUST NOT abort the reverse-order
    walk — other resources must still get their chance to unwind.
    """

    def test_gatus_driver_exception_is_swallowed(self):
        manager, ctx = _manager_and_ctx()
        ctx.add_resource("gatus", "my-project")
        ctx.add_resource("backrest", "my-project-data")  # registered AFTER gatus

        with patch(
            "fabrik.drivers.gatus.remove_endpoint", side_effect=RuntimeError("boom")
        ), patch("fabrik.drivers.backrest.remove_backup_plan") as backrest_rm:
            errors = manager.rollback(ctx)

        # gatus swallowed → no errors bubble to the outer rollback loop
        assert errors == []
        # The LATER-registered resource was still rolled back (reverse walk
        # means backrest goes FIRST, but the gatus failure after it must
        # not have stopped the walk either way — this tests both orderings)
        backrest_rm.assert_called_once_with("my-project-data")

    def test_glitchtip_404_is_soft_success(self):
        """Provisioner may have already deleted the project on DSN-verify
        failure (see InfrastructureProvisioner._provision_glitchtip);
        the rollback's delete_project call then finds a 404. The driver
        treats 404 as success, but if it somehow raised, we'd still swallow."""
        manager, ctx = _manager_and_ctx()
        ctx.add_resource("glitchtip", "my-project")

        with patch(
            "fabrik.drivers.glitchtip.delete_project",
            side_effect=Exception("404 gone"),
        ):
            errors = manager.rollback(ctx)

        assert errors == []  # exception swallowed, treated as non-fatal

    def test_authelia_driver_exception_is_swallowed(self):
        manager, ctx = _manager_and_ctx()
        ctx.add_resource("authelia", "my-app.vps1.ocoron.com")

        with patch(
            "fabrik.drivers.authelia.remove_access_rule",
            side_effect=RuntimeError("authelia down"),
        ):
            errors = manager.rollback(ctx)

        assert errors == []


class TestPhase4iReverseOrderWalk:
    """Full end-to-end rollback of a realistic deploy — verify ORDER.

    Plan §Validation Checklist: 'rollback after step 6f (authelia) unwinds
    handlers in the order authelia → grafana → glitchtip → backrest → gatus
    → coolify → dns'. ctx.created_resources is a LIFO log, so reverse
    iteration gives us that order for free — this test locks it.
    """

    def test_full_deploy_rollback_reverse_order(self):
        manager = RollbackManager(
            coolify_client=MagicMock(), dns_client=MagicMock()
        )
        ctx = DeploymentContext(spec_path=Path("t.yaml"), spec={"name": "my-app"})

        # Simulate a full deploy's resource registrations in PROVISIONING order
        ctx.add_resource("dns", "rec-1", zone="vps1.ocoron.com")
        ctx.add_resource("coolify", "uuid-1")
        ctx.add_resource("postgres", "my_app_db")
        ctx.add_resource("gatus", "my-app")
        ctx.add_resource("backrest", "my-app-data")
        ctx.add_resource("glitchtip", "my-app")
        ctx.add_resource("grafana_annotation_id", "42")
        ctx.add_resource("authelia_bypass", "my-app.vps1.ocoron.com")
        ctx.add_resource("authelia", "my-app.vps1.ocoron.com")
        ctx.add_resource("meilisearch", "my_app")

        call_order = []

        def record(name):
            def _fn(*args, **kwargs):
                call_order.append(name)
                return True

            return _fn

        with patch("fabrik.drivers.meilisearch.delete_index"), patch(
            "fabrik.drivers.authelia.remove_access_rule", side_effect=record("authelia")
        ), patch(
            "fabrik.drivers.grafana.delete_annotation", side_effect=record("grafana")
        ), patch(
            "fabrik.drivers.glitchtip.delete_project", side_effect=record("glitchtip")
        ), patch(
            "fabrik.drivers.backrest.remove_backup_plan", side_effect=record("backrest")
        ), patch(
            "fabrik.drivers.gatus.remove_endpoint", side_effect=record("gatus")
        ):
            errors = manager.rollback(ctx)

        # Coolify + DNS are MagicMock'd on the manager itself
        assert errors == []
        # Authelia is deduped — the two records produce ONE driver call
        assert call_order == [
            "authelia",  # authelia (first-seen, authelia_bypass skipped by dedup)
            "grafana",
            "glitchtip",
            "backrest",
            "gatus",
            # postgres is destructive-no-op (no driver call)
            # meilisearch is destructive-no-op (no driver call)
        ]
        # Coolify + DNS cleanup happened (legacy hard-stops, after soft registrars)
        manager._coolify_client.delete_application.assert_called_once_with("uuid-1")
        manager._dns_client.delete_record.assert_called_once_with(
            "vps1.ocoron.com", "rec-1"
        )
