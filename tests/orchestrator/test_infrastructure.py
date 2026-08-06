"""Unit tests for fabrik.orchestrator.infrastructure.

Covers:
* :func:`resolve_applicability` — shape gate + infra-override matrix.
* :class:`InfrastructureProvisioner` — per-registrar dispatch, success
  paths, soft failures, ``ctx.add_resource`` bookkeeping.
* The one hard-fail exception: glitchtip DSN-injection verification.

All driver modules are patched at the
``fabrik.orchestrator.infrastructure.<module>`` boundary via imports
inside the provisioner methods (each method does a local ``from
fabrik.drivers.<x> import ...``). Patching there keeps the tests from
needing any network, VPS, or Coolify state.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.infrastructure import (
    InfrastructureProvisioner,
    _enabled,
    format_resolved_summary,
    resolve_applicability,
)

# --------------------------------------------------------------------------- #
# _enabled                                                                     #
# --------------------------------------------------------------------------- #


class TestEnabled:
    def test_missing_key_defaults_true(self):
        assert _enabled({}, "postgres") is True

    def test_explicit_true(self):
        assert _enabled({"postgres": True}, "postgres") is True

    def test_explicit_false_is_the_only_off_switch(self):
        assert _enabled({"postgres": False}, "postgres") is False

    def test_truthy_non_false_values_still_run(self):
        """Belt-and-braces: `infra:` is override-only via explicit False.
        Any other value (1, 'yes', empty dict) must NOT skip the registrar."""
        assert _enabled({"postgres": 1}, "postgres") is True
        assert _enabled({"postgres": "disabled"}, "postgres") is True
        assert _enabled({"postgres": 0}, "postgres") is True  # 0 is not False
        assert _enabled({"postgres": None}, "postgres") is True  # None is not False

    def test_none_infra_dict_safe(self):
        """If caller passes None as infra, guard should still work."""
        assert _enabled({} or {}, "anything") is True


# --------------------------------------------------------------------------- #
# resolve_applicability — every branch in the matrix                           #
# --------------------------------------------------------------------------- #


def _spec(**overrides):
    """Default spec: a public service with no extra features."""
    base = {
        "name": "my-project",
        "domain": "my-project.vps1.ocoron.com",
        "shape": {
            "kind": "service",
            "is_public": True,
            "is_admin_dashboard": False,
            "has_bearer_api": False,
            "has_search_feature": False,
            "has_persistent_data": False,
            "needs_database": False,
        },
        "infra": {},
    }
    # Merge overrides into the right slot (flat or nested).
    if "shape" in overrides:
        base["shape"].update(overrides.pop("shape"))
    if "infra" in overrides:
        base["infra"].update(overrides.pop("infra"))
    base.update(overrides)
    return base


class TestResolveApplicability:
    def test_default_public_service_runs_gatus_glitchtip_grafana_only(self):
        r = resolve_applicability(_spec())
        # gatus: public + domain → RUN
        assert r["gatus"][0] is True
        # glitchtip: kind=service → RUN
        assert r["glitchtip"][0] is True
        # grafana: universal → RUN
        assert r["grafana"][0] is True
        # postgres/backrest/authelia/meilisearch: all gated off by defaults
        assert r["postgres"][0] is False
        assert r["backrest"][0] is False
        assert r["authelia"][0] is False
        assert r["meilisearch"][0] is False

    def test_needs_database_opt_in(self):
        r = resolve_applicability(_spec(shape={"needs_database": True}))
        assert r["postgres"][0] is True
        assert "needs_database=true" in r["postgres"][1]

    def test_persistent_data_opt_in(self):
        r = resolve_applicability(_spec(shape={"has_persistent_data": True}))
        assert r["backrest"][0] is True

    def test_admin_dashboard_opt_in_needs_domain(self):
        r_with = resolve_applicability(_spec(shape={"is_admin_dashboard": True}))
        assert r_with["authelia"][0] is True

        r_no_domain = resolve_applicability(_spec(shape={"is_admin_dashboard": True}, domain=None))
        assert r_no_domain["authelia"][0] is False
        assert "no domain" in r_no_domain["authelia"][1]

    def test_search_feature_opt_in(self):
        r = resolve_applicability(_spec(shape={"has_search_feature": True}))
        assert r["meilisearch"][0] is True

    def test_gatus_requires_both_is_public_and_domain(self):
        assert resolve_applicability(_spec(shape={"is_public": False}))["gatus"][0] is False
        assert resolve_applicability(_spec(domain=None))["gatus"][0] is False

    def test_glitchtip_kind_gate(self):
        for kind in ("service", "worker", "wordpress"):
            r = resolve_applicability(_spec(shape={"kind": kind}))
            assert r["glitchtip"][0] is True, kind
        for kind in ("static", "static-site", "docusaurus"):
            r = resolve_applicability(_spec(shape={"kind": kind}))
            assert r["glitchtip"][0] is False, kind

    def test_infra_explicit_false_disables_applicable_registrar(self):
        """The ONLY way to skip a shape-applicable registrar."""
        spec = _spec(shape={"needs_database": True}, infra={"postgres": False})
        r = resolve_applicability(spec)
        assert r["postgres"][0] is False
        assert "infra.postgres=false override" in r["postgres"][1]

    def test_infra_truthy_values_do_not_disable(self):
        spec = _spec(shape={"needs_database": True}, infra={"postgres": "no"})
        r = resolve_applicability(spec)
        assert r["postgres"][0] is True  # "no" is not False

    def test_grafana_always_runs_unless_explicitly_disabled(self):
        assert resolve_applicability(_spec())["grafana"][0] is True
        spec = _spec(infra={"grafana": False})
        assert resolve_applicability(spec)["grafana"][0] is False

    # ------------------------------------------------------------------ #
    # Plan acceptance criteria (Phase 4 validation checklist, lines
    # 2079–2080 of 2026-04-18-zero-touch-deployment.md): shape is the
    # AUTHORITATIVE signal for applicability; ``infra:`` is strictly an
    # override-OFF switch — it cannot opt a registrar IN when the shape
    # says it doesn't apply. The surrounding tests cover the override-OFF
    # path per-registrar; these two fill the two specific gaps the plan
    # checklist names by hostname/registrar.
    # ------------------------------------------------------------------ #

    def test_backrest_positive_and_override_symmetry(self):
        """Plan line 2079: ``shape.has_persistent_data=true`` runs backrest;
        setting ``infra.backrest=false`` in the same spec skips it.

        The positive half is covered by ``test_persistent_data_opt_in``.
        The override half is covered generically for ``postgres`` in
        ``test_infra_explicit_false_disables_applicable_registrar`` but
        not specifically for ``backrest``. This test locks both halves
        for backrest explicitly so a future refactor that accidentally
        hard-codes one registrar's override semantics can't silently
        skip this path."""
        # Positive: shape flag alone is sufficient.
        positive = resolve_applicability(_spec(shape={"has_persistent_data": True}))
        assert positive["backrest"][0] is True
        assert "has_persistent_data=true" in positive["backrest"][1]

        # Override: shape=true + infra.backrest=false → skipped.
        overridden = resolve_applicability(
            _spec(shape={"has_persistent_data": True}, infra={"backrest": False})
        )
        assert overridden["backrest"][0] is False
        assert "infra.backrest=false override" in overridden["backrest"][1]

    def test_infra_true_cannot_opt_in_when_shape_says_no(self):
        """Plan line 2080: spec with ``infra.gatus=true`` AND
        ``shape.is_public=false`` must NOT run gatus. ``infra:`` is
        override-OFF only — any attempt to use it as an opt-IN is
        silently ignored by design (the dispatcher only consults
        ``infra[key]`` when shape already says the registrar applies).

        This is the single most load-bearing invariant of the
        shape-vs-infra arbitration model: if it ever regressed, specs
        could drift into an inconsistent state where ``infra:`` values
        mattered more than ``shape:`` values, which would break every
        assumption the dispatcher documentation rests on."""
        # shape.is_public is the default (False); explicit infra.gatus=True
        # must NOT flip the result.
        r = resolve_applicability(_spec(shape={"is_public": False}, infra={"gatus": True}))
        assert r["gatus"][0] is False, (
            "infra.gatus=True must not opt-in gatus when shape.is_public=False. "
            "shape is authoritative; infra is override-OFF only."
        )
        assert "shape.is_public=false" in r["gatus"][1]

        # Same invariant for authelia — a second registrar to prove the
        # contract is per-registrar consistent, not a gatus-only bug fix.
        r2 = resolve_applicability(
            _spec(
                shape={"is_admin_dashboard": False},
                infra={"authelia": True},
            )
        )
        assert r2["authelia"][0] is False
        assert "shape.is_admin_dashboard=false" in r2["authelia"][1]


# --------------------------------------------------------------------------- #
# Regression: Spec.model_dump() must preserve `infra:` override (2026-05-04)   #
# --------------------------------------------------------------------------- #


class TestInfraSurvivesModelDump:
    """Regression for 2026-05-04 proxy redeploy bug.

    ``Spec`` is a pydantic model. Before this fix, ``infra`` was
    intentionally NOT a pydantic field (it was read via raw yaml.safe_load
    in the apply path). That silently broke ``destroyer._spec_to_dict``
    which uses ``spec.model_dump(mode='json')`` — the ``infra`` override
    was stripped, so ``resolve_applicability`` never saw
    ``infra.postgres: false`` and the postgres registrar ran for services
    that had explicitly disabled it. Outcome: an orphan
    ``fabrik_<name>`` Postgres database was created alongside the real
    service database. This test locks the invariant.
    """

    def test_spec_model_dump_preserves_infra_override(self, tmp_path):
        """The exact failure mode from /opt/fabrik-proxy redeploy."""
        from fabrik.spec_loader import load_spec

        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(
            "id: demo\n"
            "template: python-api\n"
            "domain: demo.vps1.example.com\n"
            "shape:\n"
            "  kind: service\n"
            "  is_public: true\n"
            "  needs_database: true\n"
            "infra:\n"
            "  postgres: false\n"
        )

        spec = load_spec(spec_file)
        dumped = spec.model_dump(mode="json")

        assert dumped["infra"] == {"postgres": False}, (
            f"infra override lost during model_dump: {dumped.get('infra')!r}"
        )

        # Round-trip through resolve_applicability — the consumer that
        # actually drives destroy + rollback.
        dumped["name"] = dumped["id"]
        resolved = resolve_applicability(dumped)
        assert resolved["postgres"][0] is False, (
            "postgres registrar ran despite infra.postgres=false"
        )
        assert "infra.postgres=false override" in resolved["postgres"][1]

    def test_spec_without_infra_dumps_to_none(self, tmp_path):
        """Scaffolded specs omit `infra:` entirely — save_spec must not invent one."""
        from fabrik.spec_loader import load_spec, save_spec

        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text("id: demo\ntemplate: python-api\ndomain: demo.vps1.example.com\n")
        spec = load_spec(spec_file)
        assert spec.infra is None

        # save_spec uses exclude_none=True — scaffolded specs stay clean.
        out = tmp_path / "out.yaml"
        save_spec(spec, out)
        assert "infra:" not in out.read_text()


# --------------------------------------------------------------------------- #
# format_resolved_summary                                                      #
# --------------------------------------------------------------------------- #


class TestFormatResolvedSummary:
    def test_lists_every_registrar_and_summary_line(self):
        summary = format_resolved_summary(resolve_applicability(_spec()))
        for reg in (
            "postgres",
            "gatus",
            "backrest",
            "glitchtip",
            "grafana",
            "authelia",
            "meilisearch",
            "watchdog",
        ):
            assert reg in summary
        # 4 default-RUN registrars on a minimal service spec with a domain:
        # gatus + glitchtip + grafana + watchdog (T-P2 artifact 12; defaults
        # to True via WatchdogConfig.enabled).
        assert "Proceeding with 4 registrars" in summary

    def test_counts_runs_not_skips(self):
        spec = _spec(
            shape={
                "needs_database": True,
                "has_persistent_data": True,
                "is_admin_dashboard": True,
                "has_search_feature": True,
            }
        )
        summary = format_resolved_summary(resolve_applicability(spec))
        # 8 should run: postgres, gatus, backrest, glitchtip, grafana (universal),
        # authelia, meilisearch, watchdog (T-P2 artifact 12; defaults to True via
        # WatchdogConfig.enabled).
        assert "Proceeding with 8 registrars" in summary


# --------------------------------------------------------------------------- #
# InfrastructureProvisioner — per-registrar dispatch                            #
# --------------------------------------------------------------------------- #


def _ctx(spec):
    """Minimal DeploymentContext with mocked spec + dry_run toggle."""
    c = DeploymentContext(spec_path=Path("/tmp/unused.yaml"))
    c.spec = spec
    c.dry_run = False
    return c


def _ok(status="created", **extra):
    return {"status": status, **extra}


class TestProvisionDispatch:
    def test_dispatches_only_applicable_registrars(self):
        """Minimal spec: only gatus + glitchtip + grafana should fire."""
        prov = InfrastructureProvisioner(deployer=MagicMock())
        ctx = _ctx(_spec())

        with (
            patch("fabrik.drivers.postgres.create_database") as pg,
            patch("fabrik.drivers.gatus.add_endpoint", return_value=_ok()) as gatus,
            patch("fabrik.drivers.backrest.add_backup_plan") as backrest,
            patch(
                "fabrik.drivers.glitchtip.create_project",
                return_value=_ok(dsn="http://x@host/1"),
            ) as gt_create,
            patch("fabrik.drivers.glitchtip.verify_dsn_injection", return_value=True),
            patch("fabrik.drivers.glitchtip.delete_project"),
            patch(
                "fabrik.drivers.grafana.post_deployment_annotation",
                return_value=_ok(annotation_id=42),
            ) as grafana,
            patch("fabrik.drivers.authelia.add_access_rule") as authelia,
            patch("fabrik.drivers.meilisearch.create_index") as meili,
            patch("fabrik.drivers.coolify.CoolifyClient"),
        ):
            # coolify_uuid must be set for glitchtip to proceed past guard
            ctx.coolify_uuid = "test-uuid"
            prov.provision(ctx)

        pg.assert_not_called()
        gatus.assert_called_once()
        backrest.assert_not_called()
        gt_create.assert_called_once()
        grafana.assert_called_once()
        authelia.assert_not_called()
        meili.assert_not_called()

    def test_dry_run_passes_through_to_every_driver(self):
        """dry_run=True must be propagated as kwarg to every driver."""
        prov = InfrastructureProvisioner(deployer=MagicMock())
        spec = _spec(
            shape={
                "needs_database": True,
                "has_persistent_data": True,
                "is_admin_dashboard": True,
                "has_bearer_api": True,
                "has_search_feature": True,
            }
        )
        ctx = _ctx(spec)
        ctx.dry_run = True

        calls = {}

        def record(name):
            def _fn(*args, **kwargs):
                calls[name] = kwargs.get("dry_run")
                return _ok(status="dry_run", dsn=None, annotation_id=None)

            return _fn

        with (
            patch("fabrik.drivers.postgres.create_database", side_effect=record("pg")),
            patch("fabrik.drivers.gatus.add_endpoint", side_effect=record("gatus")),
            patch("fabrik.drivers.backrest.add_backup_plan", side_effect=record("backrest")),
            patch("fabrik.drivers.glitchtip.create_project", side_effect=record("gt")),
            patch("fabrik.drivers.glitchtip.verify_dsn_injection"),
            patch(
                "fabrik.drivers.grafana.post_deployment_annotation",
                side_effect=record("grafana"),
            ),
            patch("fabrik.drivers.authelia.add_access_rule", side_effect=record("authelia")),
            patch("fabrik.drivers.meilisearch.create_index", side_effect=record("meili")),
        ):
            prov.provision(ctx)

        for name in ("pg", "gatus", "backrest", "gt", "grafana", "authelia", "meili"):
            assert calls.get(name) is True, f"{name} did not receive dry_run=True"

    def test_infra_override_disables_registrar(self):
        prov = InfrastructureProvisioner(deployer=MagicMock())
        spec = _spec(
            shape={"has_persistent_data": True},
            infra={"backrest": False},
        )
        ctx = _ctx(spec)

        with (
            patch("fabrik.drivers.backrest.add_backup_plan") as backrest,
            patch("fabrik.drivers.gatus.add_endpoint", return_value=_ok()),
            patch("fabrik.drivers.glitchtip.create_project", return_value=_ok(dsn=None)),
            patch(
                "fabrik.drivers.grafana.post_deployment_annotation",
                return_value=_ok(annotation_id=None),
            ),
        ):
            prov.provision(ctx)

        backrest.assert_not_called()

    def test_resource_tracking_populates_ctx(self):
        prov = InfrastructureProvisioner(deployer=MagicMock())
        spec = _spec(
            shape={
                "needs_database": True,
                "has_persistent_data": True,
                "is_admin_dashboard": True,
                "has_bearer_api": True,
                "has_search_feature": True,
            }
        )
        ctx = _ctx(spec)
        ctx.coolify_uuid = "test-uuid"

        with (
            patch("fabrik.drivers.postgres.create_database", return_value=_ok()),
            patch("fabrik.drivers.gatus.add_endpoint", return_value=_ok()),
            patch("fabrik.drivers.backrest.add_backup_plan", return_value=_ok()),
            patch(
                "fabrik.drivers.glitchtip.create_project",
                return_value=_ok(dsn="http://x@host/1"),
            ),
            patch("fabrik.drivers.glitchtip.verify_dsn_injection", return_value=True),
            patch("fabrik.drivers.glitchtip.delete_project"),
            patch(
                "fabrik.drivers.grafana.post_deployment_annotation",
                return_value=_ok(annotation_id=7),
            ),
            patch("fabrik.drivers.authelia.add_access_rule", return_value=_ok(status="added")),
            patch("fabrik.drivers.meilisearch.create_index", return_value=_ok()),
            patch("fabrik.drivers.coolify.CoolifyClient"),
        ):
            prov.provision(ctx)

        types = {r.resource_type for r in ctx.created_resources}
        assert types == {
            "postgres",
            "watchdog-db-roles",
            "subagent-ins-role",
            "gatus",
            "backrest",
            "glitchtip",
            "grafana_annotation_id",
            "authelia",
            "authelia_bypass",
            "meilisearch",
        }


# --------------------------------------------------------------------------- #
# Soft-failure semantics                                                       #
# --------------------------------------------------------------------------- #


class TestSoftFailures:
    """Drivers 1..6 are non-fatal. A raise from the driver must NOT
    propagate out of provision() — it's logged and the next registrar
    still runs.
    """

    @pytest.mark.parametrize(
        "module_fn",
        [
            "fabrik.drivers.postgres.create_database",
            "fabrik.drivers.gatus.add_endpoint",
            "fabrik.drivers.backrest.add_backup_plan",
            "fabrik.drivers.grafana.post_deployment_annotation",
            "fabrik.drivers.authelia.add_access_rule",
            "fabrik.drivers.meilisearch.create_index",
        ],
    )
    def test_each_driver_failure_is_swallowed(self, module_fn):
        prov = InfrastructureProvisioner(deployer=MagicMock())
        spec = _spec(
            shape={
                "needs_database": True,
                "has_persistent_data": True,
                "is_admin_dashboard": True,
                "has_search_feature": True,
            }
        )
        ctx = _ctx(spec)

        # Every other driver returns ok; the one under test raises.
        all_ok = {
            "fabrik.drivers.postgres.create_database": _ok(),
            "fabrik.drivers.gatus.add_endpoint": _ok(),
            "fabrik.drivers.backrest.add_backup_plan": _ok(),
            "fabrik.drivers.glitchtip.create_project": _ok(dsn=None),
            "fabrik.drivers.grafana.post_deployment_annotation": _ok(annotation_id=None),
            "fabrik.drivers.authelia.add_access_rule": _ok(status="added"),
            "fabrik.drivers.meilisearch.create_index": _ok(),
        }

        patches = []
        for fn, ret in all_ok.items():
            if fn == module_fn:
                patches.append(patch(fn, side_effect=RuntimeError("driver boom")))
            else:
                patches.append(patch(fn, return_value=ret))

        for p in patches:
            p.start()
        try:
            # Must NOT raise
            prov.provision(ctx)
        finally:
            for p in reversed(patches):
                p.stop()


# --------------------------------------------------------------------------- #
# GlitchTip DSN verify — the one HARD-fail path                                #
# --------------------------------------------------------------------------- #


class TestGlitchTipDsnInjection:
    def test_dsn_verified_is_happy_path(self):
        mock_deployer = MagicMock()
        prov = InfrastructureProvisioner(deployer=mock_deployer)
        ctx = _ctx(_spec())
        ctx.coolify_uuid = "uuid-1"

        with (
            patch(
                "fabrik.drivers.glitchtip.create_project",
                return_value=_ok(dsn="http://x@host/1"),
            ),
            patch("fabrik.drivers.glitchtip.verify_dsn_injection", return_value=True),
            patch("fabrik.drivers.glitchtip.delete_project") as del_proj,
            patch("fabrik.drivers.gatus.add_endpoint", return_value=_ok()),
            patch(
                "fabrik.drivers.grafana.post_deployment_annotation",
                return_value=_ok(annotation_id=None),
            ),
        ):
            prov.provision(ctx)

        del_proj.assert_not_called()
        mock_deployer.inject_env.assert_called_once_with(
            ctx, {"SENTRY_DSN": "http://x@host/1", "GLITCHTIP_DSN": "http://x@host/1"}
        )

    def test_dsn_verify_failure_rolls_back_and_raises(self):
        """This is THE safety-critical contract: if the env var didn't
        arrive in the container, the GlitchTip project is deleted and
        the provisioner raises so the outer orchestrator rolls the
        whole deploy back."""
        prov = InfrastructureProvisioner(deployer=MagicMock())
        ctx = _ctx(_spec())
        ctx.coolify_uuid = "uuid-1"

        with (
            patch(
                "fabrik.drivers.glitchtip.create_project",
                return_value=_ok(dsn="http://x@host/1"),
            ),
            patch("fabrik.drivers.glitchtip.verify_dsn_injection", return_value=False),
            patch("fabrik.drivers.glitchtip.delete_project") as del_proj,
            patch("fabrik.drivers.coolify.CoolifyClient"),
            patch("fabrik.drivers.gatus.add_endpoint", return_value=_ok()),
            patch(
                "fabrik.drivers.grafana.post_deployment_annotation",
                return_value=_ok(annotation_id=None),
            ),
        ):
            with pytest.raises(RuntimeError, match="SENTRY_DSN not injected"):
                prov.provision(ctx)

        del_proj.assert_called_once_with("my-project")

    def test_dsn_inject_skipped_when_coolify_uuid_missing(self):
        """Degraded-but-non-fatal path: we can't inject without the UUID,
        so we log a warning and don't try — no exception, no rollback."""
        mock_deployer = MagicMock()
        prov = InfrastructureProvisioner(deployer=mock_deployer)
        ctx = _ctx(_spec())
        ctx.coolify_uuid = None  # explicitly unset

        with (
            patch(
                "fabrik.drivers.glitchtip.create_project",
                return_value=_ok(dsn="http://x@host/1"),
            ) as create,
            patch("fabrik.drivers.glitchtip.verify_dsn_injection") as verify,
            patch("fabrik.drivers.glitchtip.delete_project") as del_proj,
            patch("fabrik.drivers.gatus.add_endpoint", return_value=_ok()),
            patch(
                "fabrik.drivers.grafana.post_deployment_annotation",
                return_value=_ok(annotation_id=None),
            ),
        ):
            prov.provision(ctx)

        create.assert_called_once()
        verify.assert_not_called()
        del_proj.assert_not_called()
        mock_deployer.inject_env.assert_not_called()

    def test_dry_run_skips_dsn_injection(self):
        prov = InfrastructureProvisioner(deployer=MagicMock())
        ctx = _ctx(_spec())
        ctx.coolify_uuid = "uuid-1"
        ctx.dry_run = True

        with (
            patch(
                "fabrik.drivers.glitchtip.create_project",
                return_value=_ok(status="dry_run", dsn=None),
            ),
            patch("fabrik.drivers.glitchtip.verify_dsn_injection") as verify,
            patch("fabrik.drivers.coolify.CoolifyClient") as coolify_cls,
            patch("fabrik.drivers.gatus.add_endpoint", return_value=_ok()),
            patch(
                "fabrik.drivers.grafana.post_deployment_annotation",
                return_value=_ok(annotation_id=None),
            ),
        ):
            prov.provision(ctx)

        verify.assert_not_called()
        coolify_cls.return_value.bulk_update_env_vars.assert_not_called()


# --------------------------------------------------------------------------- #
# Authelia ordering: bypass inserted BEFORE two_factor                         #
# --------------------------------------------------------------------------- #


class TestAutheliaOrdering:
    def test_bearer_api_bypass_goes_first(self):
        """Critical Success Factor §10: when has_bearer_api is true, the
        provisioner MUST call add_access_rule for the bypass BEFORE the
        two_factor catch-all, with insert_before_twofactor=True on the
        bypass call."""
        prov = InfrastructureProvisioner(deployer=MagicMock())
        spec = _spec(shape={"is_admin_dashboard": True, "has_bearer_api": True})
        ctx = _ctx(spec)

        calls = []

        def record(*args, **kwargs):
            calls.append(kwargs)
            return _ok(status="added")

        with (
            patch("fabrik.drivers.authelia.add_access_rule", side_effect=record),
            patch("fabrik.drivers.gatus.add_endpoint", return_value=_ok()),
            patch("fabrik.drivers.glitchtip.create_project", return_value=_ok(dsn=None)),
            patch(
                "fabrik.drivers.grafana.post_deployment_annotation",
                return_value=_ok(annotation_id=None),
            ),
        ):
            prov.provision(ctx)

        assert len(calls) == 2
        # Call 1: the bypass
        assert calls[0]["policy"] == "bypass"
        assert calls[0]["resources"] == ["^/api/"]
        assert calls[0]["insert_before_twofactor"] is True
        # Call 2: the two_factor catch-all
        assert calls[1]["policy"] == "two_factor"

    def test_no_bearer_api_means_only_two_factor_rule(self):
        prov = InfrastructureProvisioner(deployer=MagicMock())
        spec = _spec(shape={"is_admin_dashboard": True})  # has_bearer_api defaults False
        ctx = _ctx(spec)

        calls = []

        def record(*args, **kwargs):
            calls.append(kwargs)
            return _ok(status="added")

        with (
            patch("fabrik.drivers.authelia.add_access_rule", side_effect=record),
            patch("fabrik.drivers.gatus.add_endpoint", return_value=_ok()),
            patch("fabrik.drivers.glitchtip.create_project", return_value=_ok(dsn=None)),
            patch(
                "fabrik.drivers.grafana.post_deployment_annotation",
                return_value=_ok(annotation_id=None),
            ),
        ):
            prov.provision(ctx)

        assert len(calls) == 1
        assert calls[0]["policy"] == "two_factor"


# --------------------------------------------------------------------------- #
# Identifier normalization                                                     #
# --------------------------------------------------------------------------- #


class TestIdentifierNormalization:
    def test_hyphens_become_underscores_for_postgres_and_meilisearch(self):
        """Both postgres DB names and meilisearch uids disallow hyphens in
        most path contexts. The provisioner maps `my-project` → `my_project`."""
        prov = InfrastructureProvisioner(deployer=MagicMock())
        spec = _spec(
            name="my-cool-project",
            shape={"needs_database": True, "has_search_feature": True},
        )
        ctx = _ctx(spec)

        captured = {}

        def pg_fn(db_name, **kw):
            captured["pg"] = db_name
            return _ok()

        def mi_fn(uid, **kw):
            captured["mi"] = uid
            return _ok()

        with (
            patch("fabrik.drivers.postgres.create_database", side_effect=pg_fn),
            patch("fabrik.drivers.meilisearch.create_index", side_effect=mi_fn),
            patch("fabrik.drivers.gatus.add_endpoint", return_value=_ok()),
            patch("fabrik.drivers.glitchtip.create_project", return_value=_ok(dsn=None)),
            patch(
                "fabrik.drivers.grafana.post_deployment_annotation",
                return_value=_ok(annotation_id=None),
            ),
        ):
            prov.provision(ctx)

        assert captured["pg"] == "my_cool_project"
        assert captured["mi"] == "my_cool_project"


# --------------------------------------------------------------------------- #
# Orchestrator wiring smoke — DeploymentOrchestrator instantiates the provisioner
# --------------------------------------------------------------------------- #


class TestOrchestratorWiring:
    def test_orchestrator_injects_default_provisioner(self):
        from fabrik.orchestrator import DeploymentOrchestrator
        from fabrik.orchestrator.infrastructure import InfrastructureProvisioner

        # Skip other managers to avoid heavy side effects in __init__
        orch = DeploymentOrchestrator()
        assert isinstance(orch.infrastructure_provisioner, InfrastructureProvisioner)

    def test_orchestrator_accepts_override(self):
        from fabrik.orchestrator import DeploymentOrchestrator

        sentinel = MagicMock()
        orch = DeploymentOrchestrator(infrastructure_provisioner=sentinel)
        assert orch.infrastructure_provisioner is sentinel
