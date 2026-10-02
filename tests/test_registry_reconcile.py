"""plan-2 Phase B — the hourly postgres allocation reconcile and its cron wiring.

The reconcile tests run the REAL ``register_allocation_if_absent`` against an
``ssh`` fake on ``fabrik.drivers.postgres``, so the in-lock path is exercised;
``_db_owner`` is patched on ``fabrik.registry_reconcile``. The cron tests load
``scripts/audit_all_registrars.py`` by path and patch its collaborators. No SSH,
no network.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from fabrik import registry_reconcile as rr
from fabrik.audit import AuditResult
from fabrik.drivers import postgres as pg_driver
from fabrik.spec_loader import Depends, Shape, Spec

REPO = Path(__file__).resolve().parents[1]
REGISTRY = {
    "version": 1,
    "allocations": {"translator": {"owner": "fabrik", "spec_id": "translator"}},
}


def _orphan(db: str) -> dict[str, AuditResult]:
    return {
        "postgres": AuditResult(
            status="drift",
            actual={"db_name": db, "found": True, "registry_entry": None, "in_registry": False},
        )
    }


class _Registry:
    """An ``ssh`` fake serving one registry payload; records writes."""

    def __init__(self, payload: dict):
        self.payload = payload
        self.writes: list[str] = []

    def __call__(self, cmd, *, dry_run: bool = False):
        if "cat " in cmd:
            return json.dumps(self.payload)
        self.writes.append(cmd)
        return ""


def _reconcile(
    audits, claims=None, *, claims_complete=True, dry_run=False, owner="zitadel", payload=None
):
    reg = _Registry(payload if payload is not None else REGISTRY)
    claims = (
        claims
        if claims is not None
        else {a["postgres"].actual["db_name"]: [s] for s, a in audits.items()}
    )
    with (
        patch.object(pg_driver, "ssh", side_effect=reg),
        patch.object(rr, "_db_owner", return_value=owner) as owner_lookup,
    ):
        heals = rr.reconcile_postgres(
            audits, claims, claims_complete=claims_complete, dry_run=dry_run
        )
    return heals, reg, owner_lookup


class TestReconcile:
    def test_orphan_is_registered_with_its_real_owner(self):
        # B1
        heals, reg, _ = _reconcile({"zitadel": _orphan("zitadel")}, owner="zitadel_owner")
        assert [(h.spec_id, h.db, h.outcome) for h in heals] == [
            ("zitadel", "zitadel", "registered")
        ]
        tee = [c for c in reg.writes if "tee " in c]
        assert tee and '"user": "zitadel_owner"' in tee[0] and '"spec_id": "zitadel"' in tee[0]
        assert "registered by the hourly reconcile 20" in tee[0]
        assert '"translator": {' in tee[0]

    def test_entry_present_at_the_locked_write_is_left_untouched(self):
        # B2 — the audit saw no entry, but one exists by the time of the write.
        payload = {"version": 1, "allocations": {"zitadel": {"owner": "manual", "spec_id": "x"}}}
        heals, reg, _ = _reconcile({"zitadel": _orphan("zitadel")}, payload=payload)
        assert [h.outcome for h in heals] == ["already-present"]
        assert reg.writes == []

    def test_dry_run_writes_nothing_and_reports_would_register(self):
        # B3 (reconcile half)
        heals, reg, owner_lookup = _reconcile({"zitadel": _orphan("zitadel")}, dry_run=True)
        assert [h.outcome for h in heals] == ["would-register"]
        assert reg.writes == []
        owner_lookup.assert_not_called()

    def test_failed_owner_lookup_or_write_is_failed_with_its_reason(self):
        # B4 (reconcile half)
        heals, reg, _ = _reconcile({"zitadel": _orphan("zitadel")}, owner=None)
        assert [(h.outcome, h.reason) for h in heals] == [("failed", "owner-unresolved")]
        assert reg.writes == []

        with (
            patch.object(pg_driver, "ssh", side_effect=RuntimeError("ssh down")),
            patch.object(rr, "_db_owner", return_value="zitadel"),
        ):
            heals = rr.reconcile_postgres(
                {"zitadel": _orphan("zitadel")},
                {"zitadel": ["zitadel"]},
                claims_complete=True,
                dry_run=False,
            )
        assert [(h.outcome, h.reason) for h in heals] == [("failed", "RuntimeError")]

    def test_stale_entry_missing_and_present_results_are_not_touched(self):
        # B6
        audits = {
            "stale": {
                "postgres": AuditResult(
                    status="drift", actual={"db_name": "stale", "found": False, "in_registry": True}
                )
            },
            "gone": {
                "postgres": AuditResult(
                    status="missing",
                    actual={"db_name": "gone", "found": False, "in_registry": False},
                )
            },
            "ok": {
                "postgres": AuditResult(
                    status="present", actual={"db_name": "ok", "found": True, "in_registry": True}
                )
            },
            "na": {"postgres": AuditResult(status="n/a")},
            "unread": {
                "postgres": AuditResult(
                    status="present", actual={"db_name": "unread", "found": True}
                )
            },
        }
        heals, reg, owner_lookup = _reconcile(audits, claims={})
        assert heals == []
        assert reg.writes == []
        owner_lookup.assert_not_called()

    def test_shared_database_is_refused_naming_the_other_claimants(self):
        # B7 — `main` claimed by two specs, one of which audited `unknown`.
        audits = {
            "exam-coach": _orphan("main"),
            "compliance-ops": {"postgres": AuditResult(status="unknown")},
        }
        claims = {"main": ["compliance-ops", "exam-coach"]}
        heals, reg, owner_lookup = _reconcile(audits, claims)
        assert [(h.outcome, h.reason) for h in heals] == [("shared", "compliance-ops")]
        assert reg.writes == []
        owner_lookup.assert_not_called()

    def test_incomplete_claims_fail_every_candidate(self):
        # B7 — a spec failed to load or audit, or a name failed to resolve.
        heals, reg, owner_lookup = _reconcile(
            {"zitadel": _orphan("zitadel")}, claims_complete=False
        )
        assert [(h.outcome, h.reason) for h in heals] == [("failed", "claims-unresolved")]
        assert reg.writes == []
        owner_lookup.assert_not_called()


class TestClaims:
    def _spec(self, sid: str, postgres=None) -> Spec:
        return Spec.model_construct(
            id=sid,
            name=None,
            shape=Shape(needs_database=True),
            depends=Depends.model_construct(postgres=postgres)
            if postgres is not None
            else Depends(),
        )

    def test_claims_map_database_names_to_spec_ids(self):
        claim_map, unresolved = rr.claims(
            [
                self._spec("exam-coach", "main"),
                self._spec("compliance-ops", "main"),
                self._spec("zitadel"),
            ]
        )
        assert claim_map == {"main": ["exam-coach", "compliance-ops"], "zitadel": ["zitadel"]}
        assert unresolved == []

    @pytest.mark.filterwarnings("ignore:Pydantic serializer warnings")
    def test_non_string_depends_postgres_is_unresolved_without_raising(self):
        # B7 — unbuildable through load_spec (pydantic refuses it), so built with model_construct.
        claim_map, unresolved = rr.claims([self._spec("bad", True), self._spec("zitadel")])
        assert unresolved == ["bad"]
        assert claim_map == {"zitadel": ["zitadel"]}


class TestMode:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, "report"),
            ("report", "report"),
            ("apply", "apply"),
            ("off", "off"),
            ("yes", "report"),
            ("APPLY", "report"),
        ],
    )
    def test_mode_defaults_to_report(self, monkeypatch, value, expected):
        # B3 — unset or unknown never writes.
        if value is None:
            monkeypatch.delenv("FABRIK_REGISTRY_RECONCILE", raising=False)
        else:
            monkeypatch.setenv("FABRIK_REGISTRY_RECONCILE", value)
        assert rr.mode() == expected


# ---------------------------------------------------------------------------
# The cron script's wiring
# ---------------------------------------------------------------------------


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "audit_all_registrars", REPO / "scripts" / "audit_all_registrars.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Cron:
    """Run the script's ``main`` over fake specs; capture the pushed payload and curl argv."""

    def __init__(self, tmp_path, monkeypatch, *, specs: dict, mode: str, reconcile=None):
        self.mod = _load_script()
        self.pushed: list[tuple[list[str], str]] = []
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        for sid in specs:
            (specs_dir / f"{sid}.yaml").write_text("id: x\n")
        monkeypatch.setattr(self.mod, "SPECS_DIR", specs_dir)
        monkeypatch.setattr(self.mod, "METRICS_OUT_FILE", tmp_path / "metrics.txt")
        monkeypatch.setenv("FABRIK_REGISTRY_RECONCILE", mode)

        def fake_load(path):
            obj = specs[Path(path).stem]
            if isinstance(obj, Exception):
                raise obj
            return obj

        def fake_run(cmd, *, stdin, **_kw):
            self.pushed.append((cmd, stdin.read().decode()))
            return subprocess.CompletedProcess(cmd, 0, b"", b"")

        self.audit_calls: list[str] = []

        def fake_audit_all(spec):
            self.audit_calls.append(spec.id)
            return (
                _orphan(spec.id)
                if self.audit_calls.count(spec.id) == 1
                else {"postgres": AuditResult(status="present")}
            )

        monkeypatch.setattr(self.mod, "load_spec", fake_load)
        monkeypatch.setattr(self.mod, "audit_all", fake_audit_all)
        monkeypatch.setattr(self.mod.subprocess, "run", fake_run)
        monkeypatch.setattr(self.mod.shutil, "which", lambda _n: "/usr/bin/ssh")
        if reconcile is not None:
            monkeypatch.setattr(self.mod.registry_reconcile, "reconcile_postgres", reconcile)

    def run(self) -> tuple[int, str, list[str]]:
        rc = self.mod.main()
        cmd, body = self.pushed[-1]
        return rc, body, cmd


def _spec_obj(sid: str) -> Spec:
    return Spec.model_construct(
        id=sid, name=None, shape=Shape(needs_database=True), depends=Depends()
    )


class TestCron:
    def test_clean_run_puts_and_carries_the_last_success_timestamp(self, tmp_path, monkeypatch):
        # B5
        heal = [rr.HealResult("zitadel", "zitadel", "registered")]
        cron = _Cron(
            tmp_path,
            monkeypatch,
            specs={"zitadel": _spec_obj("zitadel")},
            mode="apply",
            reconcile=lambda *a, **k: heal,
        )
        rc, body, cmd = cron.run()
        assert rc == 0
        assert "-X PUT" in cmd[-1]
        assert "\nfabrik_audit_last_success_timestamp_seconds " in body
        assert "\nfabrik_audit_spec_errors 0\n" in body
        assert (
            'fabrik_registry_heal_total{spec_id="zitadel",db="zitadel",outcome="registered"} 1'
            in body
        )
        # the registered spec is re-audited and its drift series cleared in the same push
        assert cron.audit_calls == ["zitadel", "zitadel"]
        assert 'fabrik_audit_drift_total{spec_id="zitadel",registrar="postgres"} 0' in body

    def test_spec_error_withholds_the_timestamp_and_fails_claims(self, tmp_path, monkeypatch):
        # B5 + B7 — a spec YAML that fails to load (e.g. depends.postgres: true) sets error_count.
        seen: dict = {}
        real = rr.reconcile_postgres

        def spy(audits, claims, *, claims_complete, dry_run):
            seen.update(claims_complete=claims_complete, dry_run=dry_run)
            return real(audits, claims, claims_complete=claims_complete, dry_run=dry_run)

        specs = {
            "zitadel": _spec_obj("zitadel"),
            "bad": ValueError("depends.postgres must be a string"),
        }
        cron = _Cron(tmp_path, monkeypatch, specs=specs, mode="apply", reconcile=spy)
        rc, body, _ = cron.run()
        assert rc == 0
        assert seen == {"claims_complete": False, "dry_run": False}
        assert "fabrik_audit_last_success_timestamp_seconds" not in body
        assert "\nfabrik_audit_spec_errors 1\n" in body
        assert (
            'fabrik_registry_heal_failed{spec_id="zitadel",db="zitadel",reason="claims-unresolved"} 1'
            in body
        )

    def test_reconcile_crash_still_pushes_the_audit_without_a_timestamp(
        self, tmp_path, monkeypatch
    ):
        # B4 + B5
        def boom(*_a, **_k):
            raise RuntimeError("reconcile exploded")

        cron = _Cron(
            tmp_path,
            monkeypatch,
            specs={"zitadel": _spec_obj("zitadel")},
            mode="apply",
            reconcile=boom,
        )
        rc, body, _ = cron.run()
        assert rc == 0
        assert 'fabrik_audit_drift_total{spec_id="zitadel",registrar="postgres"} 1' in body
        assert "fabrik_audit_last_success_timestamp_seconds" not in body

    def test_failed_heal_renders_its_failure_series(self, tmp_path, monkeypatch):
        # B4 (render half)
        heal = [rr.HealResult("zitadel", "zitadel", "failed", "owner-unresolved")]
        cron = _Cron(
            tmp_path,
            monkeypatch,
            specs={"zitadel": _spec_obj("zitadel")},
            mode="apply",
            reconcile=lambda *a, **k: heal,
        )
        _, body, _ = cron.run()
        assert (
            'fabrik_registry_heal_failed{spec_id="zitadel",db="zitadel",reason="owner-unresolved"} 1'
            in body
        )
        assert 'fabrik_audit_drift_total{spec_id="zitadel",registrar="postgres"} 1' in body

    @pytest.mark.parametrize(
        ("value", "dry_run"), [("report", True), ("junk", True), ("apply", False)]
    )
    def test_mode_selects_dry_run(self, tmp_path, monkeypatch, value, dry_run):
        # B3 (cron half)
        seen: list[bool] = []
        cron = _Cron(
            tmp_path,
            monkeypatch,
            specs={"zitadel": _spec_obj("zitadel")},
            mode=value,
            reconcile=lambda a, c, *, claims_complete, dry_run: seen.append(dry_run) or [],
        )
        cron.run()
        assert seen == [dry_run]

    def test_off_does_not_run_the_reconcile(self, tmp_path, monkeypatch):
        # B3
        calls: list = []
        cron = _Cron(
            tmp_path,
            monkeypatch,
            specs={"zitadel": _spec_obj("zitadel")},
            mode="off",
            reconcile=lambda *a, **k: calls.append(1) or [],
        )
        _, body, _ = cron.run()
        assert calls == []
        assert "fabrik_registry_heal_total{" not in body
