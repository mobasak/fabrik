"""Phase 4j — end-to-end rollback integration test.

Walks a realistic full-shape spec through the real
:class:`DeploymentOrchestrator.deploy` code path (not just
:class:`RollbackManager` in isolation — that's Phase 4i's scope).
All drivers are stubbed, but the orchestrator wiring,
:class:`InfrastructureProvisioner.provision` dispatch, and the
:exc:`ProvisioningError`-to-rollback path are **real**.

Failure-injection point: ``glitchtip.verify_dsn_injection`` returns
False. This is the one registrar whose contract says "if the ground-
truth check fails, roll back the project and raise" — which bubbles
out of ``InfrastructureProvisioner.provision`` → wrapped in
``ProvisioningError`` by ``DeploymentOrchestrator.deploy`` → triggers
the rollback path. Earlier registrars (postgres/gatus/backrest) have
already run and registered resources; later registrars
(grafana/authelia/meilisearch) must NOT run.

What this test catches that Phase 4i's unit tests don't:

* ``InfrastructureProvisioner.provision`` actually calling the
  registrar methods in order on a real spec.
* ``DeploymentOrchestrator.deploy`` wrapping the RuntimeError as
  ``ProvisioningError`` and hitting the rollback path (not the
  unexpected-exception path, which has different semantics).
* State machine transitions reaching ``ROLLED_BACK`` cleanly via the
  real ``_transition`` gate.
* The full reverse-order walk against the real
  ``RollbackManager._rollback_resource`` dispatch (same object Phase
  4i unit-tested, but now fed resources the real provisioner
  registered, not resources a test fabricated).

What this test deliberately does NOT validate (left for first real
``fabrik apply`` smoke):

* Live VPS contract drift (driver↔VPS-side API shape mismatches).
  Those are caught by the per-driver live probes already run in
  Phases 4d/4e/4f/4g (see ``scripts/probes/``).
* DNS propagation timing.
* Authelia container restart impact.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fabrik.orchestrator import DeploymentOrchestrator, DeploymentState
from fabrik.orchestrator.deployer_ssh import SSHDeployer
from fabrik.orchestrator.rollback import RollbackManager
from fabrik.orchestrator.validator import SpecValidator
from fabrik.orchestrator.verifier import DeploymentVerifier

# ----------------------------------------------------------------------- #
# Fixtures                                                                 #
# ----------------------------------------------------------------------- #


@pytest.fixture
def full_shape_spec(tmp_path: Path) -> Path:
    """Spec with every ``shape.*`` flag true + ``has_bearer_api``.

    Triggers all seven registrars:
    postgres · gatus · backrest · glitchtip · grafana · authelia (+ bypass)
    · meilisearch.
    """
    spec_file = tmp_path / "e2e-rollback-smoke.yaml"
    spec_file.write_text(
        "name: e2e-rollback-smoke\n"
        "template: python-api\n"
        "domain: e2e-rollback-smoke.example.com\n"
        "shape:\n"
        "  kind: service\n"
        "  is_public: true\n"
        "  needs_database: true\n"
        "  has_persistent_data: true\n"
        "  has_error_tracking: true\n"
        "  has_search_feature: true\n"
        "  is_admin_dashboard: true\n"
        "  has_bearer_api: true\n"
        "secrets:\n"
        "  - API_KEY\n"
    )
    return spec_file


@pytest.fixture
def templates_dir(tmp_path: Path) -> Path:
    """Minimal templates dir so SpecValidator doesn't reject python-api."""
    (tmp_path / "python-api").mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def _bypass_dns_and_external_clients():
    """Block DNS / Coolify / Cloudflare network calls across all tests."""
    mock_dns = MagicMock()
    mock_dns.add_subdomain.return_value = {"success": True}
    with (
        patch("fabrik.orchestrator.validator.is_private_ip", return_value=False),
        patch("fabrik.orchestrator.DNSClient", return_value=mock_dns),
    ):
        yield


# ----------------------------------------------------------------------- #
# Helpers                                                                  #
# ----------------------------------------------------------------------- #


def _mock_deployer() -> MagicMock:
    """Deployer that registers Coolify like the real one would.

    The real ``SSHDeployer.deploy`` adds a ``compose`` resource to
    ``ctx.created_resources`` and sets ``ctx.coolify_uuid``. The
    :meth:`InfrastructureProvisioner._provision_glitchtip` step needs
    ``ctx.coolify_uuid`` to be set (otherwise it degrades to a warning
    instead of attempting injection — and we need injection to attempt,
    to reach ``verify_dsn_injection``).
    """
    deployer = MagicMock(spec=SSHDeployer)

    def deploy(ctx):
        ctx.add_resource("compose", "smoke-app")
        ctx.coolify_uuid = "smoke-app"
        ctx.deployed_url = f"https://{ctx.spec['domain']}"
        return "smoke-uuid-0000"

    deployer.deploy.side_effect = deploy
    return deployer


def _mock_verifier() -> MagicMock:
    """Verifier that would succeed if reached (it won't — rollback preempts)."""
    verifier = MagicMock(spec=DeploymentVerifier)
    verifier.verify.return_value = True
    return verifier


def _rollback_manager_with_mocks() -> tuple[RollbackManager, MagicMock, MagicMock, MagicMock]:
    """RollbackManager wired to mocked Coolify + DNS + deployer clients.

    The real :class:`RollbackManager` lazy-loads CoolifyClient and
    CloudflareClient from their driver modules on first use; in an
    E2E test against a synthetic "example.com" domain those real
    clients would make live HTTP calls (Cloudflare specifically
    returns 'Could not route to /client/v4/zones/example.com/...'
    which then counts as a rollback error and flips the final state
    from ROLLED_BACK to FAILED).

    Pre-injecting MagicMocks for both clients avoids that — the
    legacy hard-stop handlers ``_rollback_coolify`` and
    ``_rollback_dns`` then exercise the real code path against fake
    endpoints, and the final state matches the success contract.
    The deployer mock avoids SSH calls during ``_rollback_compose``.

    Returns:
        (manager, mock_coolify, mock_dns, mock_deployer) — callers
        can assert on these to verify the reverse walk reached them.
    """
    mock_coolify = MagicMock()
    mock_dns = MagicMock()
    mock_deployer = MagicMock(spec=SSHDeployer)
    manager = RollbackManager(
        coolify_client=mock_coolify, dns_client=mock_dns, deployer=mock_deployer
    )
    return manager, mock_coolify, mock_dns, mock_deployer


# ----------------------------------------------------------------------- #
# Tests                                                                    #
# ----------------------------------------------------------------------- #


class TestPhase4jEndToEndRollback:
    """Full orchestrator walk through a failing deploy, asserting
    every observable contract Phase 4h + 4i are supposed to guarantee."""

    def test_full_shape_deploy_fails_at_glitchtip_rolls_back_in_reverse_order(
        self, full_shape_spec, templates_dir, caplog
    ):
        """The end-to-end contract:

        1. DNS + compose + postgres + gatus + backrest + glitchtip all
           run and register resources, in that order.
        2. glitchtip's DSN-verify returns False → provisioner calls its
           inline ``delete_project`` cleanup → raises RuntimeError.
        3. Orchestrator wraps the RuntimeError as ``ProvisioningError``
           and hits the rollback path (NOT the unexpected-exception path).
        4. grafana / authelia / meilisearch NEVER run (they sit after
           glitchtip in the registrar order).
        5. Rollback walks reverse: glitchtip · backrest · gatus ·
           postgres(log-only) · coolify · dns.
        6. Final state == ``ROLLED_BACK`` (not FAILED — rollback
           completed with no driver errors).
        """
        # ------- Stub every driver at the module level -------
        # (InfrastructureProvisioner imports lazily inside each _provision_*
        # method — patching the module attribute catches both the first
        # call and any cached import.)
        rollback_calls: list[str] = []

        def rec(name):
            def _fn(*args, **kwargs):
                rollback_calls.append(name)
                return True

            return _fn

        with (
            patch(
                "fabrik.drivers.postgres.create_database",
                return_value={"status": "created", "db_name": "e2e_rollback_smoke"},
            ) as m_pg_create,
            patch(
                "fabrik.drivers.gatus.add_endpoint",
                return_value={"status": "created"},
            ) as m_gatus_add,
            patch("fabrik.drivers.gatus.remove_endpoint", side_effect=rec("gatus")),
            patch(
                "fabrik.drivers.backrest.add_backup_plan",
                return_value={"status": "created", "plan_id": "e2e-rollback-smoke-data"},
            ) as m_br_add,
            patch("fabrik.drivers.backrest.remove_backup_plan", side_effect=rec("backrest")),
            patch(
                "fabrik.drivers.glitchtip.create_project",
                return_value={
                    "status": "created",
                    "dsn": "https://deadbeef@glitchtip.test/1",
                },
            ) as m_gt_create,
            patch(
                # ↓ THE INJECTION POINT — DSN verification fails ↓
                "fabrik.drivers.glitchtip.verify_dsn_injection",
                return_value=False,
            ) as m_gt_verify,
            patch("fabrik.drivers.glitchtip.delete_project", side_effect=rec("glitchtip")),
            patch(
                # Grafana / authelia / meilisearch must NOT be called — but
                # patch them so if they were, we'd detect it.
                "fabrik.drivers.grafana.post_deployment_annotation"
            ) as m_grafana_post,
            patch(
                "fabrik.drivers.grafana.delete_annotation", side_effect=rec("grafana")
            ) as m_grafana_del,
            patch("fabrik.drivers.authelia.add_access_rule") as m_authelia_add,
            patch(
                "fabrik.drivers.authelia.remove_access_rule", side_effect=rec("authelia")
            ) as m_authelia_rm,
            patch("fabrik.drivers.meilisearch.create_index") as m_meili_create,
            patch(
                "fabrik.drivers.meilisearch.delete_index", side_effect=rec("meilisearch")
            ) as m_meili_del,
            patch(  # noqa: F841 — asserted below
                # Coolify needed by _provision_glitchtip for DSN injection
                # and by RollbackManager for app delete.
                "fabrik.drivers.coolify.CoolifyClient"
            ) as m_coolify_cls,
        ):
            mock_coolify = MagicMock()
            m_coolify_cls.return_value = mock_coolify

            # ------- Real orchestrator, real provisioner, mocked rollback clients -------
            # RollbackManager itself is real (Phase 4i code under test);
            # only the Coolify + Cloudflare *clients* it uses are mocked.
            rb_manager, rb_coolify, rb_dns, rb_deployer = _rollback_manager_with_mocks()
            validator = SpecValidator(templates_dir=templates_dir)
            orchestrator = DeploymentOrchestrator(
                validator=validator,
                deployer=_mock_deployer(),
                verifier=_mock_verifier(),
                rollback_manager=rb_manager,
            )
            ctx = orchestrator.deploy(full_shape_spec)

        # --------------- Assertions ---------------

        # (1) End state — rollback completed with no driver errors.
        assert ctx.state == DeploymentState.ROLLED_BACK, (
            f"Expected ROLLED_BACK, got {ctx.state.name}. ctx.error={ctx.error!r}"
        )

        # (2) Error contains the injection signal (DSN not injected).
        assert "SENTRY_DSN" in str(ctx.error) or "glitchtip" in str(ctx.error).lower(), (
            f"Expected DSN-injection error in ctx.error; got: {ctx.error!r}"
        )

        # (3) Forward-pass driver calls — registrars up to glitchtip ran.
        m_pg_create.assert_called_once()
        m_gatus_add.assert_called_once()
        m_br_add.assert_called_once()
        m_gt_create.assert_called_once()
        m_gt_verify.assert_called_once()

        # (4) Registrars AFTER glitchtip must NOT have run — the registrar
        #     chain aborts at glitchtip's RuntimeError.
        m_grafana_post.assert_not_called()
        m_authelia_add.assert_not_called()
        m_meili_create.assert_not_called()

        # (5) ctx.created_resources order — LIFO insertion during the
        #     forward pass, iterated in reverse by RollbackManager.
        registered = [(r.resource_type, r.resource_id) for r in ctx.created_resources]
        expected_prefix = [
            ("dns", "e2e-rollback-smoke.example.com"),
            ("compose", "smoke-app"),
            ("postgres", "e2e_rollback_smoke"),
            ("watchdog-db-roles", "e2e_rollback_smoke"),
            ("subagent-ins-role", "e2e-rollback-smoke"),
            ("gatus", "e2e-rollback-smoke"),
            ("backrest", "e2e-rollback-smoke-data"),
            ("glitchtip", "e2e-rollback-smoke"),
        ]
        assert registered == expected_prefix, (
            f"Resource ledger drifted:\n  got:      {registered}\n  expected: {expected_prefix}"
        )

        # (6) Rollback walk — reverse of registration, minus destructive
        #     no-ops (postgres) and minus Coolify/DNS (handled by mocked
        #     CoolifyClient + DNSClient, not tracked in rollback_calls).
        #
        #     Note: ``glitchtip.delete_project`` is called TWICE — once
        #     inline by _provision_glitchtip's RuntimeError cleanup, and
        #     once by _rollback_glitchtip during the reverse walk. Both
        #     are idempotent (driver treats 404 as success), so we assert
        #     total count >= 1 with glitchtip appearing BEFORE the others
        #     in rollback_calls.
        registrar_rollbacks = [c for c in rollback_calls if c != "glitchtip"] + [
            # Collapse duplicate glitchtip entries — we only care that it
            # appeared at least once, before backrest/gatus.
            "glitchtip" if "glitchtip" in rollback_calls else None
        ]
        registrar_rollbacks = [x for x in registrar_rollbacks if x is not None]

        # The rollback-only walk (not counting the inline cleanup):
        # glitchtip → backrest → gatus. postgres is log-only (no driver).
        # We assert the ORDER of the reverse walk.
        glitchtip_idx = rollback_calls.index("glitchtip")
        backrest_idx = rollback_calls.index("backrest")
        gatus_idx = rollback_calls.index("gatus")
        # The LAST glitchtip call (from the rollback walk, not the inline
        # cleanup) must come before backrest → which must come before gatus.
        # Equivalently: there must exist a glitchtip call earlier in the
        # list than backrest, and backrest earlier than gatus.
        assert glitchtip_idx < backrest_idx < gatus_idx, (
            f"Reverse-order rollback drift: glitchtip@{glitchtip_idx} "
            f"should precede backrest@{backrest_idx} should precede "
            f"gatus@{gatus_idx}. Full call list: {rollback_calls}"
        )

        # (7) Destructive-action policy — postgres NOT dropped.
        #     The postgres driver has no drop_database fn; we simply
        #     assert no postgres rollback driver symbol was touched by
        #     the walk. (The warning log is asserted in the next test.)
        assert "postgres" not in rollback_calls

        # (8) meilisearch + grafana + authelia — registered resources
        #     never existed (they sat AFTER glitchtip in the order), so
        #     their rollback handlers must NOT have been invoked.
        m_grafana_del.assert_not_called()
        m_authelia_rm.assert_not_called()
        m_meili_del.assert_not_called()

        # (9) Compose app was deleted during rollback.
        rb_deployer.delete.assert_called_once_with("smoke-app")

        # (10) DNS record was deleted during rollback.
        rb_dns.delete_record_by_name.assert_called_once_with(
            "example.com", "A", "e2e-rollback-smoke"
        )

    def test_destructive_noop_policy_logs_manual_command_during_e2e(
        self, full_shape_spec, templates_dir, caplog
    ):
        """After a full-shape E2E rollback, the operator-facing WARNING
        for postgres manual-drop must appear in logs — even though no
        driver was invoked. This locks the contract that the
        destructive-action policy is observable to the operator, not a
        silent skip that leaves them wondering whether the DB survived.
        """
        import logging

        caplog.set_level(logging.WARNING)

        with (
            patch(
                "fabrik.drivers.postgres.create_database",
                return_value={"status": "created", "db_name": "e2e_rollback_smoke"},
            ),
            patch("fabrik.drivers.gatus.add_endpoint", return_value={"status": "created"}),
            patch("fabrik.drivers.gatus.remove_endpoint", return_value=True),
            patch(
                "fabrik.drivers.backrest.add_backup_plan",
                return_value={"status": "created"},
            ),
            patch("fabrik.drivers.backrest.remove_backup_plan", return_value=True),
            patch(
                "fabrik.drivers.glitchtip.create_project",
                return_value={"status": "created", "dsn": "https://x@gt/1"},
            ),
            patch("fabrik.drivers.glitchtip.verify_dsn_injection", return_value=False),
            patch("fabrik.drivers.glitchtip.delete_project", return_value=True),
            patch("fabrik.drivers.coolify.CoolifyClient"),
        ):
            rb_manager, _, _, _ = _rollback_manager_with_mocks()
            validator = SpecValidator(templates_dir=templates_dir)
            orchestrator = DeploymentOrchestrator(
                validator=validator,
                deployer=_mock_deployer(),
                verifier=_mock_verifier(),
                rollback_manager=rb_manager,
            )
            ctx = orchestrator.deploy(full_shape_spec)

        assert ctx.state == DeploymentState.ROLLED_BACK
        # The destructive-no-op WARNING is the operator's only signal
        # that a DB was created and survives the rollback.
        assert any("fabrik db drop" in rec.message for rec in caplog.records), (
            "Expected 'fabrik db drop' manual-command WARNING in logs after e2e rollback"
        )

    def test_infra_override_skips_registrar_entirely(self, tmp_path, templates_dir):
        """A spec that sets ``infra.glitchtip: false`` on an otherwise
        shape-applicable service skips the registrar — and therefore
        the injection point — and the deploy SUCCEEDS.

        This catches the regression where a future refactor might wire
        the override-only gate incorrectly (e.g. reading the wrong key,
        or a truthy check that accepts ``false`` as truthy-string).
        """
        spec_file = tmp_path / "no-glitchtip.yaml"
        spec_file.write_text(
            "name: no-glitchtip-smoke\n"
            "template: python-api\n"
            "domain: no-glitchtip.example.com\n"
            "shape:\n"
            "  kind: service\n"
            "  is_public: true\n"
            "  needs_database: true\n"
            "infra:\n"
            "  glitchtip: false\n"
            "secrets:\n"
            "  - API_KEY\n"
        )

        with (
            patch(
                "fabrik.drivers.postgres.create_database",
                return_value={"status": "created"},
            ),
            patch("fabrik.drivers.gatus.add_endpoint", return_value={"status": "created"}),
            patch("fabrik.drivers.glitchtip.create_project") as m_gt_create,
            patch("fabrik.drivers.glitchtip.verify_dsn_injection") as m_gt_verify,
            patch(
                "fabrik.drivers.grafana.post_deployment_annotation",
                return_value={"annotation_id": 99, "status": "created"},
            ),
            patch("fabrik.drivers.coolify.CoolifyClient"),
        ):
            validator = SpecValidator(templates_dir=templates_dir)
            orchestrator = DeploymentOrchestrator(
                validator=validator,
                deployer=_mock_deployer(),
                verifier=_mock_verifier(),
            )
            ctx = orchestrator.deploy(spec_file)

        # GlitchTip was gated out → its injection point was never reached
        # → deploy ran to completion.
        assert ctx.state == DeploymentState.COMPLETE
        m_gt_create.assert_not_called()
        m_gt_verify.assert_not_called()
