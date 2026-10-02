"""Tests for fabrik.audit — per-registrar drift audit module (T2-02 G-G2).

All audits are mocked at the SSH/HTTP boundary so tests run hermetically
on WSL with no VPS network calls.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

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
    audit_watchdog,
)
from fabrik.orchestrator.infrastructure import _REGISTRAR_ORDER

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

_PROBE = "sudo docker ps --format '{{.Names}}'"


@pytest.fixture(autouse=True)
def _fresh_container_cache():
    # _resolve_container memoises per process; without this every test inherits
    # whatever an earlier test left behind and passes or fails by run order.
    audit._CONTAINER_CACHE.clear()
    audit._CONTAINER_PROBE_FAILED.clear()
    yield
    audit._CONTAINER_CACHE.clear()
    audit._CONTAINER_PROBE_FAILED.clear()


_RUNNING = "postgres-main\nredis-main\nauthelia\nbackrest"


def _vps(answer, names: str = _RUNNING):
    """An `_ssh_check` stand-in: the container probe sees ``names`` running; every other
    command gets ``answer`` (a fixed ``(ok, out)`` tuple, or a callable taking the command)."""

    def fake(cmd, **_kw):
        if cmd == _PROBE:
            return (True, names)
        return answer(cmd) if callable(answer) else answer

    return fake


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
            patch.object(audit, "_ssh_check", side_effect=_vps((True, "1"))),
            self._registry_mock("my_svc"),
        ):
            r = audit_postgres(_spec_dict(id="my-svc"))
        assert r.status == "present"
        assert r.actual["db_name"] == "my_svc"  # dashes → underscores
        assert r.actual["found"] is True

    def test_missing_when_db_absent(self):
        with (
            patch.object(audit, "_ssh_check", side_effect=_vps((True, ""))),
            self._registry_mock(None),
        ):
            r = audit_postgres(_spec_dict(id="my-svc"))
        assert r.status == "missing"

    def test_unknown_when_ssh_fails(self):
        with patch.object(audit, "_ssh_check", side_effect=_vps((False, "Connection refused"))):
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
    """W-5c4ad6a6 (D-518): the audit reports ``backrest.coverage_findings``, read-only."""

    @staticmethod
    def _run(spec, ret=("present", [], {"covered_by": {"/v": "docker-volumes"}}), raises=None):
        calls: list[dict] = []

        def fake(name, db, *, target_host, hub_host):
            calls.append({"name": name, "db": db, "target_host": target_host, "hub_host": hub_host})
            if raises:
                raise raises
            return ret

        with patch("fabrik.drivers.backrest.coverage_findings", side_effect=fake):
            r = audit_backrest(spec)
        return r, calls

    def test_b1_present_names_the_covering_plans(self):
        r, calls = self._run(_spec_dict(shape={"has_persistent_data": True}))
        assert r.status == "present"
        assert "docker-volumes" in r.detail
        assert r.actual["covered_by"] == {"/v": "docker-volumes"}
        assert calls[0]["name"] == "test-svc"

    def test_b2_an_unprotected_path_is_drift(self):
        r, _ = self._run(
            _spec_dict(shape={"has_persistent_data": True}),
            ret=("drift", ["unprotected: /srv/x"], {"covered_by": {}}),
        )
        assert r.status == "drift"
        assert "unprotected: /srv/x" in r.detail

    def test_b3_a_paper_plan_is_drift(self):
        r, _ = self._run(
            _spec_dict(shape={"has_persistent_data": True}),
            ret=("drift", ["paper plan test-svc-data: remove it"], {}),
        )
        assert r.status == "drift"
        assert "paper plan test-svc-data: remove it" in r.detail

    @pytest.mark.parametrize("status", ["missing", "unknown"])
    def test_b4_missing_and_unknown_pass_through(self, status):
        r, _ = self._run(_spec_dict(shape={"has_persistent_data": True}), ret=(status, ["x"], {}))
        assert r.status == status

    def test_b4_a_raising_check_is_unknown(self):
        r, _ = self._run(_spec_dict(shape={"has_persistent_data": True}), raises=ValueError("bad"))
        assert r.status == "unknown"
        assert "bad" in r.detail

    def test_b6_the_database_is_checked_only_when_postgres_runs(self):
        shape = {"has_persistent_data": True, "needs_database": True}
        _, calls = self._run(_spec_dict(shape=shape))
        assert calls[0]["db"] == "test_svc"
        _, calls = self._run(_spec_dict(shape=shape, infra={"postgres": False}))
        assert calls[0]["db"] is None

    def test_n_a_when_backrest_is_not_applicable(self):
        r, calls = self._run(_spec_dict(shape={"has_persistent_data": False}))
        assert r.status == "n/a" and calls == []

    def test_b8_the_target_comes_from_the_fabrik_root_state_file(self, monkeypatch, tmp_path):
        import json

        root, cwd = tmp_path / "root", tmp_path / "elsewhere"
        for base, vps in ((root, "vps3"), (cwd, "vps9")):  # the cwd copy is a decoy
            (base / ".fabrik" / "state").mkdir(parents=True)
            (base / ".fabrik" / "state" / "test-svc.json").write_text(
                json.dumps({"target_vps": vps})
            )
        monkeypatch.chdir(cwd)
        monkeypatch.setattr("fabrik.config.FABRIK_ROOT", root)
        monkeypatch.setenv("FABRIK_AUDIT_VPS", "hubalias")
        spec = {**_spec_dict(shape={"has_persistent_data": True}), "target_vps": "vps2"}

        _, calls = self._run(spec)
        assert (calls[0]["target_host"], calls[0]["hub_host"]) == ("vps3", "hubalias")

        (root / ".fabrik" / "state" / "test-svc.json").unlink()
        _, calls = self._run(spec)
        assert (calls[0]["target_host"], calls[0]["hub_host"]) == ("vps2", "hubalias")

        _, calls = self._run(_spec_dict(shape={"has_persistent_data": True}))
        assert (calls[0]["target_host"], calls[0]["hub_host"]) == ("hubalias", "hubalias")

        _, calls = self._run({**spec, "target_vps": "vps1"})
        assert calls[0]["target_host"] == "hubalias"


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
        with patch.object(audit, "_ssh_check", side_effect=_vps((True, config))):
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
        with patch.object(audit, "_ssh_check", side_effect=_vps((True, config))):
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
        with patch.object(audit, "_ssh_check", side_effect=_vps((True, config))):
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

        # Phase 1 — pre-reconcile audit. Most registrars return "missing".
        def pre_responses(cmd, **_):
            # _resolve_container lists every running name and filters locally.
            if cmd == _PROBE:
                return (True, "postgres-main-test\nauthelia-test\nbackrest-test")
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
            if cmd == _PROBE:
                return (True, "postgres-main-test\nauthelia-test\nbackrest-test")
            if "docker ps" in cmd and "watchdog" in cmd:
                # D3: watchdog sidecar now audited — report present post-reconcile
                return (True, "test-svc-watchdog")
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


class TestAuditWatchdog:
    """W-c6d27660: docker runs alone, so a docker failure is `unknown`, never `missing`."""

    def test_present_when_sidecar_listed(self):
        with patch.object(audit, "_ssh_check", return_value=(True, "test-svc-watchdog")):
            r = audit_watchdog(_spec_dict())
        assert r.status == "present"

    def test_missing_when_docker_lists_nothing(self):
        with patch.object(audit, "_ssh_check", return_value=(True, "")):
            r = audit_watchdog(_spec_dict())
        assert r.status == "missing"

    def test_docker_failure_is_unknown_not_missing(self):
        seen: list[str] = []

        def probe(cmd, **_kw):
            seen.append(cmd)
            return (False, "Cannot connect to the Docker daemon")

        with patch.object(audit, "_ssh_check", side_effect=probe):
            r = audit_watchdog(_spec_dict())
        assert r.status == "unknown"
        assert "|" not in seen[0]  # nothing downstream of docker can mask its exit status


class TestResolveContainerCache:
    """W-c6d27660: only an ANSWERED probe is cached. A failed probe (ssh blip, docker refused)
    returns None, is held back for _PROBE_RETRY_S, then retried; an absent container costs one probe."""

    def test_failed_probe_is_retried_not_cached(self, monkeypatch):
        clock = [1000.0]
        monkeypatch.setattr(audit, "_now", lambda: clock[0])
        answers = iter([(False, "ssh: connect timed out"), (True, "postgres-main")])
        monkeypatch.setattr(audit, "_ssh_check", lambda cmd, **_kw: next(answers))
        assert audit._resolve_container("postgres-main") is None
        clock[0] += audit._PROBE_RETRY_S
        assert audit._resolve_container("postgres-main") == "postgres-main"

    def test_docker_failure_over_working_ssh_is_not_read_as_absent(self, monkeypatch):
        """`docker ps | grep | head` exits 0 through `head` when docker itself fails, so the
        failure read as 'container not running' and was cached for the run. The probe runs
        docker alone: its non-zero exit must reach the resolver and nothing is cached."""
        seen: list[str] = []

        def probe(cmd, **_kw):
            seen.append(cmd)
            return (False, "Cannot connect to the Docker daemon")

        monkeypatch.setattr(audit, "_ssh_check", probe)
        assert audit._resolve_container("postgres-main") is None
        assert "postgres-main" not in audit._CONTAINER_CACHE
        assert seen == [_PROBE]

    def test_failed_probe_is_held_back_within_the_retry_window(self, monkeypatch):
        clock = [1000.0]
        monkeypatch.setattr(audit, "_now", lambda: clock[0])
        calls: list[str] = []

        def probe(cmd, **_kw):
            calls.append(cmd)
            return (False, "ssh: connect timed out")

        monkeypatch.setattr(audit, "_ssh_check", probe)
        for _ in range(5):
            assert audit._resolve_container("postgres-main") is None
            clock[0] += 10
        assert len(calls) == 1  # 40 s elapsed: still inside the hold
        clock[0] += audit._PROBE_RETRY_S
        assert audit._resolve_container("postgres-main") is None
        assert len(calls) == 2

    def test_absent_container_is_probed_once(self, monkeypatch):
        calls: list[str] = []

        def probe(cmd, **_kw):
            calls.append(cmd)
            return (True, "redis-main\nauthelia")

        monkeypatch.setattr(audit, "_ssh_check", probe)
        assert audit._resolve_container("backrest") is None
        assert audit._resolve_container("backrest") is None
        assert len(calls) == 1

    @pytest.mark.parametrize(
        ("names", "expected"),
        [
            ("postgres-main", "postgres-main"),
            ("redis-main\npostgres-main-abc123", "postgres-main-abc123"),
            ("postgres-main2\npostgres-mainx", None),
        ],
    )
    def test_matches_bare_name_and_legacy_suffix_only(self, monkeypatch, names, expected):
        monkeypatch.setattr(audit, "_ssh_check", lambda cmd, **_kw: (True, names))
        assert audit._resolve_container("postgres-main") == expected
