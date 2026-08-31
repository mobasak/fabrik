"""Tests for fabrik.audit — per-registrar drift audit module (T2-02 G-G2).

All audits are mocked at the SSH/HTTP boundary so tests run hermetically
on WSL with no VPS network calls.
"""

from __future__ import annotations

from unittest.mock import patch

from fabrik import audit
from fabrik.audit import (
    AuditResult,
    audit_all,
    audit_authelia,
    audit_backrest,
    audit_gatus,
    audit_glitchtip,
    audit_grafana,
    audit_meilisearch,
    audit_postgres,
    audit_prometheus,
    audit_redis,
)
from fabrik.orchestrator.infrastructure import _REGISTRAR_ORDER

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


def _spec_dict(
    *,
    id: str = "test-svc",
    domain: str = "test.example.com",
    shape: dict | None = None,
    infra: dict | None = None,
) -> dict:
    return {
        "id": id,
        "name": id,
        "domain": domain,
        "kind": "service",
        "template": "python-api",
        "shape": shape
        or {
            "needs_database": True,
            "needs_cache": False,
            "has_search_feature": False,
            "is_admin_dashboard": True,
            "is_public": True,
            "has_persistent_data": False,
            "exposes_metrics": True,
        },
        **({"infra": infra} if infra else {}),
    }


# ─────────────────────────────────────────────────────────────────────────────
# audit_grafana — pure n/a, no patches needed
# ─────────────────────────────────────────────────────────────────────────────


class TestAuditGrafana:
    def test_returns_na_with_reason(self):
        r = audit_grafana(_spec_dict())
        assert r.status == "n/a"
        assert "decorative" in r.detail or "point-in-time" in r.detail


# ─────────────────────────────────────────────────────────────────────────────
# audit_postgres
# ─────────────────────────────────────────────────────────────────────────────


class TestAuditPostgres:
    @staticmethod
    def _registry_mock(db_name: str | None):
        """Patch the postgres driver's SSH boundary to return a registry that
        either contains ``db_name`` (when set) or is empty (when None).

        T4-01: audit_postgres now cross-references allocations.json. To keep
        the legacy DB-exists-implies-present test green, mock the registry
        to contain the expected db_name.
        """
        import json as _json

        from fabrik.drivers import postgres as _pg

        payload = {
            "version": 1,
            "allocations": {
                db_name: {
                    "owner": "fabrik",
                    "spec_id": "test-spec",
                    "user": "postgres",
                    "notes": "",
                }
            }
            if db_name
            else {},
        }
        return patch.object(_pg, "ssh", return_value=_json.dumps(payload))

    def test_present_when_db_exists(self):
        with (
            patch.object(audit, "_ssh_check", return_value=(True, "1")),
            self._registry_mock("my_svc"),
        ):
            r = audit_postgres(_spec_dict(id="my-svc"))
        assert r.status == "present"
        assert r.actual["db_name"] == "my_svc"  # dashes → underscores
        assert r.actual["found"] is True

    def test_missing_when_db_absent(self):
        with (
            patch.object(audit, "_ssh_check", return_value=(True, "")),
            self._registry_mock(None),
        ):
            r = audit_postgres(_spec_dict(id="my-svc"))
        assert r.status == "missing"

    def test_unknown_when_ssh_fails(self):
        with patch.object(audit, "_ssh_check", return_value=(False, "Connection refused")):
            r = audit_postgres(_spec_dict())
        assert r.status == "unknown"
        assert "Connection refused" in r.detail

    def test_na_when_shape_says_skip(self):
        spec = _spec_dict(shape={"needs_database": False})
        r = audit_postgres(spec)
        assert r.status == "n/a"


# ─────────────────────────────────────────────────────────────────────────────
# audit_redis
# ─────────────────────────────────────────────────────────────────────────────


class TestAuditRedis:
    def test_present_when_slot_assigned(self):
        spec = _spec_dict(shape={"needs_cache": True})
        with patch.object(audit, "_ssh_check", return_value=(True, '{"test-svc": 5, "other": 3}')):
            r = audit_redis(spec)
        assert r.status == "present"
        assert r.actual["db_index"] == 5

    def test_missing_when_no_slot(self):
        spec = _spec_dict(shape={"needs_cache": True})
        with patch.object(audit, "_ssh_check", return_value=(True, '{"other": 3}')):
            r = audit_redis(spec)
        assert r.status == "missing"

    def test_unknown_on_invalid_json(self):
        spec = _spec_dict(shape={"needs_cache": True})
        with patch.object(audit, "_ssh_check", return_value=(True, "not json")):
            r = audit_redis(spec)
        assert r.status == "unknown"
        assert "invalid" in r.detail.lower()


# ─────────────────────────────────────────────────────────────────────────────
# audit_gatus
# ─────────────────────────────────────────────────────────────────────────────


class TestAuditGatus:
    def test_present_when_yaml_exists(self):
        with patch.object(audit, "_ssh_check", return_value=(True, "present")):
            r = audit_gatus(_spec_dict())
        assert r.status == "present"

    def test_missing_when_yaml_absent(self):
        with patch.object(audit, "_ssh_check", return_value=(True, "missing")):
            r = audit_gatus(_spec_dict())
        assert r.status == "missing"


# ─────────────────────────────────────────────────────────────────────────────
# audit_backrest
# ─────────────────────────────────────────────────────────────────────────────


class TestAuditBackrest:
    @staticmethod
    def _fake_ssh(config: str, missing: str = ""):
        """Answer all THREE distinct SSH calls audit_backrest now makes.

        1. `docker ps` container lookup — must return a real name: `_resolve_container`
           caches per-process in a module-level dict, so returning "" here poisons
           `_CONTAINER_CACHE['backrest']` for every later test in the session.
        2. `cat /config/config.json` — the plan config.
        3. the `test -e` path probe — stdout lists only the MISSING paths, so empty
           output means every path exists.

        A single-return mock cannot express this: it replays the config JSON as the
        probe's stdout, which parses as 'all these paths are missing'.
        """

        def fake(cmd, **kw):
            if "docker ps" in cmd:
                return (True, "backrest")
            if "config.json" in cmd:
                return (True, config)
            return (True, missing)

        return fake

    def test_present_when_plan_in_config(self):
        spec = _spec_dict(shape={"has_persistent_data": True})
        config = '{"plans": [{"id": "test-svc", "paths": ["/data"]}]}'
        with patch.object(audit, "_ssh_check", side_effect=self._fake_ssh(config)):
            r = audit_backrest(spec)
        assert r.status == "present"
        assert r.actual["paths"] == ["/data"]

    def test_present_for_the_id_the_registrar_actually_creates(self):
        """`_provision_backrest` writes `f"{name}-data"` (infrastructure.py:773).

        Matching only a bare `sid` made `missing` structurally unreachable-to-avoid:
        every service with a real plan audited as MISSING (zitadel, live 2026-08-31).
        """
        spec = _spec_dict(shape={"has_persistent_data": True})
        config = '{"plans": [{"id": "test-svc-data", "paths": ["/opt/test-svc/data"]}]}'
        with patch.object(audit, "_ssh_check", side_effect=self._fake_ssh(config)):
            r = audit_backrest(spec)
        assert r.status == "present"
        assert r.expected["plan_id"] == "test-svc-data"
        assert r.actual["paths"] == ["/opt/test-svc/data"]

    def test_drift_when_plan_exists_but_its_path_does_not(self):
        """A plan pointed at a non-existent directory is a PAPER BACKUP.

        `_provision_backrest` hardcodes /opt/<name>/data regardless of where the
        service persists, so a named-volume service gets a green plan that archives
        nothing (live: /opt/zitadel/data absent, zitadel-data plan pointing at it).
        """
        spec = _spec_dict(shape={"has_persistent_data": True})
        config = '{"plans": [{"id": "test-svc-data", "paths": ["/opt/test-svc/data"]}]}'

        with patch.object(
            audit, "_ssh_check", side_effect=self._fake_ssh(config, missing="/opt/test-svc/data")
        ):
            r = audit_backrest(spec)
        assert r.status == "drift"
        assert "archives NOTHING" in r.detail
        assert r.actual["missing_paths"] == ["/opt/test-svc/data"]

    def test_path_probe_failure_does_not_invent_drift(self):
        """Fail-open: a broken probe must not manufacture a finding."""
        spec = _spec_dict(shape={"has_persistent_data": True})
        config = '{"plans": [{"id": "test-svc-data", "paths": ["/opt/test-svc/data"]}]}'

        def fake_ssh(cmd, **kw):
            if "docker ps" in cmd:
                return (True, "backrest")
            if "config.json" in cmd:
                return (True, config)
            return (False, "ssh: connection reset")

        with patch.object(audit, "_ssh_check", side_effect=fake_ssh):
            r = audit_backrest(spec)
        assert r.status == "present"

    def test_missing_when_no_plan(self):
        spec = _spec_dict(shape={"has_persistent_data": True})
        config = '{"plans": [{"id": "other"}]}'
        with patch.object(audit, "_ssh_check", return_value=(True, config)):
            r = audit_backrest(spec)
        assert r.status == "missing"


# ─────────────────────────────────────────────────────────────────────────────
# audit_glitchtip
# ─────────────────────────────────────────────────────────────────────────────


class TestAuditGlitchtip:
    def test_unknown_when_no_token(self, monkeypatch):
        monkeypatch.delenv("GLITCHTIP_API_TOKEN", raising=False)
        r = audit_glitchtip(_spec_dict())
        assert r.status == "unknown"
        assert "TOKEN" in r.detail

    def test_present_on_http_200(self, monkeypatch):
        monkeypatch.setenv("GLITCHTIP_API_TOKEN", "test-token")
        # Mock the requests.get inside the function
        import requests as _requests

        class FakeResp:
            status_code = 200

        with patch.object(_requests, "get", return_value=FakeResp()):
            r = audit_glitchtip(_spec_dict())
        assert r.status == "present"

    def test_missing_on_http_404(self, monkeypatch):
        monkeypatch.setenv("GLITCHTIP_API_TOKEN", "test-token")
        import requests as _requests

        class FakeResp:
            status_code = 404

        with patch.object(_requests, "get", return_value=FakeResp()):
            r = audit_glitchtip(_spec_dict())
        assert r.status == "missing"


# ─────────────────────────────────────────────────────────────────────────────
# audit_authelia
# ─────────────────────────────────────────────────────────────────────────────


class TestAuditAuthelia:
    def test_present_when_rule_for_domain(self):
        config = """
access_control:
  rules:
    - domain: test.example.com
      policy: two_factor
"""
        with patch.object(audit, "_ssh_check", return_value=(True, config)):
            r = audit_authelia(_spec_dict(domain="test.example.com"))
        assert r.status == "present"
        assert len(r.actual["rules"]) == 1

    def test_missing_when_no_rule(self):
        config = """
access_control:
  rules:
    - domain: other.example.com
      policy: two_factor
"""
        with patch.object(audit, "_ssh_check", return_value=(True, config)):
            r = audit_authelia(_spec_dict(domain="test.example.com"))
        assert r.status == "missing"

    def test_list_domain_form(self):
        config = """
access_control:
  rules:
    - domain:
        - a.example.com
        - test.example.com
      policy: bypass
"""
        with patch.object(audit, "_ssh_check", return_value=(True, config)):
            r = audit_authelia(_spec_dict(domain="test.example.com"))
        assert r.status == "present"


# ─────────────────────────────────────────────────────────────────────────────
# audit_meilisearch
# ─────────────────────────────────────────────────────────────────────────────


class TestAuditMeilisearch:
    def test_present_on_http_200(self):
        spec = _spec_dict(shape={"has_search_feature": True})
        # First _ssh_check returns container name, second returns http status
        with patch.object(
            audit, "_ssh_check", side_effect=[(True, "meilisearch-xyz"), (True, "200")]
        ):
            r = audit_meilisearch(spec)
        assert r.status == "present"

    def test_missing_on_http_404(self):
        spec = _spec_dict(shape={"has_search_feature": True})
        with patch.object(
            audit, "_ssh_check", side_effect=[(True, "meilisearch-xyz"), (True, "404")]
        ):
            r = audit_meilisearch(spec)
        assert r.status == "missing"


# ─────────────────────────────────────────────────────────────────────────────
# audit_prometheus
# ─────────────────────────────────────────────────────────────────────────────


class TestAuditPrometheus:
    def test_present_when_job_listed(self):
        spec = _spec_dict(shape={"exposes_metrics": True, "is_public": True})
        grep_output = "  - job_name: test-svc\n  - job_name: prometheus"
        with patch.object(audit, "_ssh_check", return_value=(True, grep_output)):
            r = audit_prometheus(spec)
        assert r.status == "present"

    def test_present_with_fabrik_prefix(self):
        spec = _spec_dict(shape={"exposes_metrics": True, "is_public": True})
        grep_output = "  - job_name: fabrik-test-svc"
        with patch.object(audit, "_ssh_check", return_value=(True, grep_output)):
            r = audit_prometheus(spec)
        assert r.status == "present"

    def test_missing_when_job_absent(self):
        spec = _spec_dict(shape={"exposes_metrics": True, "is_public": True})
        grep_output = "  - job_name: prometheus\n  - job_name: node"
        with patch.object(audit, "_ssh_check", return_value=(True, grep_output)):
            r = audit_prometheus(spec)
        assert r.status == "missing"


# ─────────────────────────────────────────────────────────────────────────────
# audit_all aggregator
# ─────────────────────────────────────────────────────────────────────────────


class TestAuditAll:
    def test_returns_all_registrars(self):
        # Count is asserted against _REGISTRAR_ORDER (single source of truth) so
        # this never drifts when a registrar is added/removed — the keys-equality
        # assert already proves the set is exactly right.
        with patch.object(audit, "_ssh_check", return_value=(True, "")):
            results = audit_all(_spec_dict())
        assert set(results.keys()) == set(_REGISTRAR_ORDER)
        assert len(results) == len(_REGISTRAR_ORDER)

    def test_never_raises_even_if_audit_blows_up(self):
        # Force one audit to raise; aggregator must catch it.
        original = audit.audit_postgres

        def boom(_spec):
            raise RuntimeError("synthetic explosion")

        audit.audit_postgres = boom
        audit._AUDIT_FUNCS["postgres"] = boom
        try:
            with patch.object(audit, "_ssh_check", return_value=(True, "")):
                results = audit_all(_spec_dict())
            assert results["postgres"].status == "unknown"
            assert "synthetic explosion" in results["postgres"].detail
        finally:
            audit.audit_postgres = original
            audit._AUDIT_FUNCS["postgres"] = original

    def test_grafana_is_always_na(self):
        with patch.object(audit, "_ssh_check", return_value=(True, "")):
            results = audit_all(_spec_dict())
        assert results["grafana"].status == "n/a"


# ─────────────────────────────────────────────────────────────────────────────
# AuditResult.to_dict
# ─────────────────────────────────────────────────────────────────────────────


class TestAuditResultSerialization:
    def test_to_dict_round_trips(self):
        r = AuditResult(
            status="present",
            detail="found",
            expected={"x": 1},
            actual={"y": 2},
        )
        d = r.to_dict()
        assert d == {
            "status": "present",
            "detail": "found",
            "expected": {"x": 1},
            "actual": {"y": 2},
        }


# ─────────────────────────────────────────────────────────────────────────────
# Audit → reconcile → re-audit roundtrip (Epic Brief SC-1 + SC-3)
# ─────────────────────────────────────────────────────────────────────────────


class TestAuditReconcileRoundtrip:
    """The full lifecycle ``fabrik audit-registrars`` → reconcile → re-audit.

    Simulates the reconcile step (which IRL would call
    DeploymentOrchestrator.refresh_infrastructure) by switching the mock
    SSH responses between the two audits. The test asserts that the
    second audit reports zero ``missing`` after the simulated reconcile.
    """

    def test_zero_missing_after_simulated_reconcile(self):
        spec = _spec_dict(
            shape={
                "needs_database": True,
                "needs_cache": False,
                "has_search_feature": False,
                "is_admin_dashboard": True,
                "is_public": True,
                "has_persistent_data": False,
                "exposes_metrics": True,
            }
        )
        # Clear the container cache so each Phase gets a fresh probe.
        audit._CONTAINER_CACHE.clear()

        # Phase 1 — pre-reconcile audit. Most registrars return "missing".
        def pre_responses(cmd, **_):
            # _resolve_container probes use `docker ps ... grep -E '^<prefix>(-|$)'`
            if "docker ps" in cmd and "grep" in cmd:
                if "postgres-main" in cmd:
                    return (True, "postgres-main-test")
                if "authelia" in cmd:
                    return (True, "authelia-test")
                if "backrest" in cmd:
                    return (True, "backrest-test")
            if "pg_database" in cmd:
                return (True, "")  # db missing
            if "gatus" in cmd and "test -f" in cmd:
                return (True, "missing")
            if "authelia" in cmd and "cat /config" in cmd:
                return (True, "access_control:\n  rules: []\n")
            if "prometheus" in cmd:
                return (True, "")  # no jobs match
            return (True, "")

        with patch.object(audit, "_ssh_check", side_effect=pre_responses):
            pre = audit_all(spec)
        pre_missing = sorted(reg for reg, r in pre.items() if r.status == "missing")
        assert "postgres" in pre_missing
        assert "gatus" in pre_missing
        assert "authelia" in pre_missing

        # Phase 2 — simulated reconcile (we just switch the mock outputs).
        # Phase 3 — re-audit. All previously-missing registrars now present.
        # Clear cache so resolve_container reprobes (which is realistic — the
        # reconcile may have created the containers in question).
        audit._CONTAINER_CACHE.clear()

        def post_responses(cmd, **_):
            if "docker ps" in cmd and "grep" in cmd:
                if "postgres-main" in cmd:
                    return (True, "postgres-main-test")
                if "authelia" in cmd:
                    return (True, "authelia-test")
                if "backrest" in cmd:
                    return (True, "backrest-test")
                if (
                    "watchdog" in cmd
                ):  # D3: watchdog sidecar now audited — report present post-reconcile
                    return (True, "present")
            if "pg_database" in cmd:
                return (True, "1")
            if "gatus" in cmd and "test -f" in cmd:
                return (True, "present")
            if "authelia" in cmd and "cat /config" in cmd:
                return (
                    True,
                    "access_control:\n  rules:\n    - domain: test.example.com\n      policy: two_factor\n",
                )
            if "prometheus" in cmd:
                return (True, "  - job_name: test-svc")
            return (True, "")

        with patch.object(audit, "_ssh_check", side_effect=post_responses):
            post = audit_all(spec)
        post_missing = [reg for reg, r in post.items() if r.status == "missing"]
        assert post_missing == [], (
            f"Expected zero missing after reconcile; still missing: {post_missing}"
        )
