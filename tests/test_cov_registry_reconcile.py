"""Coverage sweep for ``fabrik.registry_reconcile`` — behaviour that
``tests/test_registry_reconcile.py`` does not assert.

Hermetic: ``_db_owner`` and ``register_allocation_if_absent`` are patched on the module under
test, so no ssh, docker or network is touched.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from fabrik import registry_reconcile as rr
from fabrik.audit import AuditResult


def _audit(db="appdb", *, status="drift", found=True, in_registry=False, **extra):
    actual = {"db_name": db, "found": found, "in_registry": in_registry, **extra}
    return {"postgres": AuditResult(status=status, actual=actual)}


def _run(audits, claims=None, *, complete=True, dry_run=False, owner="own", wrote=True):
    reg = MagicMock(return_value=wrote)
    lookup = MagicMock(return_value=owner)
    with (
        patch.object(rr, "register_allocation_if_absent", reg),
        patch.object(rr, "_db_owner", lookup),
    ):
        heals = rr.reconcile_postgres(
            audits, claims or {}, claims_complete=complete, dry_run=dry_run
        )
    return heals, reg, lookup


def _dict_spec(sid, *, db=True, postgres=None, name=None):
    spec = {"id": sid, "shape": {"needs_database": db}}
    if name:
        spec["name"] = name
    if postgres:
        spec["depends"] = {"postgres": postgres}
    return spec


class TestHealResult:
    def test_reason_defaults_to_empty(self):
        h = rr.HealResult("s", "d", "registered")
        assert (h.spec_id, h.db, h.outcome, h.reason) == ("s", "d", "registered", "")

    def test_equality_is_by_value(self):
        assert rr.HealResult("s", "d", "shared", "x") == rr.HealResult("s", "d", "shared", "x")
        assert rr.HealResult("s", "d", "shared") != rr.HealResult("s", "d", "failed")


class TestMode:
    def test_unknown_value_warns_once_with_the_value(self, monkeypatch, caplog):
        monkeypatch.setenv("FABRIK_REGISTRY_RECONCILE", "bogus")
        with caplog.at_level(logging.WARNING, logger=rr.logger.name):
            assert rr.mode() == "report"
        warns = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warns) == 1 and "'bogus'" in warns[0].getMessage()

    @pytest.mark.parametrize("value", ["apply", "report", "off"])
    def test_valid_value_does_not_warn(self, monkeypatch, caplog, value):
        monkeypatch.setenv("FABRIK_REGISTRY_RECONCILE", value)
        with caplog.at_level(logging.WARNING, logger=rr.logger.name):
            assert rr.mode() == value
        assert not caplog.records

    def test_empty_string_is_not_a_mode(self, monkeypatch):
        monkeypatch.setenv("FABRIK_REGISTRY_RECONCILE", "")
        assert rr.mode() == "report"

    def test_whitespace_padded_value_is_not_trimmed(self, monkeypatch):
        monkeypatch.setenv("FABRIK_REGISTRY_RECONCILE", " apply ")
        assert rr.mode() == "report"


class TestClaims:
    def test_empty_input(self):
        assert rr.claims([]) == ({}, [])

    def test_accepts_a_generator(self):
        claim_map, unresolved = rr.claims(_dict_spec(s, postgres="main") for s in ("a", "b"))
        assert claim_map == {"main": ["a", "b"]}
        assert unresolved == []

    def test_hyphenated_id_becomes_underscored_database(self):
        assert rr.claims([_dict_spec("my-app")])[0] == {"my_app": ["my-app"]}

    def test_explicit_depends_postgres_wins_and_is_not_rewritten(self):
        assert rr.claims([_dict_spec("my-app", postgres="shared-db")])[0] == {
            "shared-db": ["my-app"]
        }

    def test_name_is_used_when_id_missing(self):
        spec = {"name": "named-one", "shape": {"needs_database": True}}
        assert rr.claims([spec]) == ({"named_one": ["named-one"]}, [])

    def test_spec_without_postgres_registrar_is_skipped_not_unresolved(self):
        claim_map, unresolved = rr.claims([_dict_spec("nodb", db=False), _dict_spec("db")])
        assert claim_map == {"db": ["db"]}
        assert unresolved == []

    def test_bad_depends_type_is_unresolved_and_others_still_map(self):
        bad = {"id": "bad", "shape": {"needs_database": True}, "depends": ["x"]}
        claim_map, unresolved = rr.claims([bad, _dict_spec("ok")])
        assert unresolved == ["bad"]
        assert claim_map == {"ok": ["ok"]}

    def test_unresolved_spec_is_logged_with_its_id(self, caplog):
        bad = {"id": "bad", "shape": {"needs_database": True}, "depends": {"postgres": 5}}
        with caplog.at_level(logging.WARNING, logger=rr.logger.name):
            rr.claims([bad])
        assert any("bad" in r.getMessage() for r in caplog.records)

    def test_unresolvable_object_falls_back_to_str_for_the_label(self):
        class Weird:
            def __str__(self):
                return "weird-thing"

        assert rr.claims([Weird()]) == ({}, ["weird-thing"])

    def test_same_spec_twice_is_listed_twice(self):
        claim_map, _ = rr.claims([_dict_spec("a"), _dict_spec("a")])
        assert claim_map == {"a": ["a", "a"]}


class TestReconcileSelection:
    def test_no_audits_gives_no_results(self):
        heals, reg, lookup = _run({})
        assert heals == []
        reg.assert_not_called()
        lookup.assert_not_called()

    def test_spec_without_postgres_entry_is_skipped(self):
        heals, reg, _ = _run({"s": {"redis": AuditResult(status="drift")}})
        assert heals == []
        reg.assert_not_called()

    def test_actual_none_is_skipped(self):
        heals, _, _ = _run({"s": {"postgres": AuditResult(status="drift", actual=None)}})
        assert heals == []

    @pytest.mark.parametrize("found", [False, None, "yes", 1])
    def test_found_must_be_literally_true(self, found):
        heals, reg, _ = _run({"s": _audit(found=found)})
        assert heals == []
        reg.assert_not_called()

    @pytest.mark.parametrize("in_registry", [True, None, 0, "no"])
    def test_in_registry_must_be_literally_false(self, in_registry):
        heals, reg, _ = _run({"s": _audit(in_registry=in_registry)})
        assert heals == []
        reg.assert_not_called()

    @pytest.mark.parametrize("status", ["present", "missing", "unknown", "n/a"])
    def test_only_drift_status_is_a_candidate(self, status):
        heals, reg, _ = _run({"s": _audit(status=status)}, {"appdb": ["s"]})
        assert heals == []
        reg.assert_not_called()

    @pytest.mark.parametrize("db", [None, "", 7, ["x"]])
    def test_non_string_or_empty_db_is_db_name_missing(self, db):
        heals, reg, lookup = _run({"s": _audit(db=db)})
        assert heals == [rr.HealResult("s", "", "failed", "db-name-missing")]
        reg.assert_not_called()
        lookup.assert_not_called()

    def test_db_name_missing_ignores_complete_claims_and_dry_run(self):
        heals, _, _ = _run({"s": _audit(db=None)}, complete=False, dry_run=True)
        assert [(h.outcome, h.reason) for h in heals] == [("failed", "db-name-missing")]

    def test_results_follow_audit_order_one_per_candidate(self):
        audits = {"b": _audit("db_b"), "skip": _audit(status="present"), "a": _audit("db_a")}
        claims = {"db_a": ["a"], "db_b": ["b"]}
        heals, _, _ = _run(audits, claims, dry_run=True)
        assert [(h.spec_id, h.db) for h in heals] == [("b", "db_b"), ("a", "db_a")]

    def test_mixed_outcomes_in_one_pass(self):
        audits = {"ok": _audit("d1"), "sh": _audit("d2"), "nm": _audit(None)}
        claims = {"d1": ["ok"], "d2": ["sh", "other"]}
        heals, _, _ = _run(audits, claims)
        assert [h.outcome for h in heals] == ["registered", "shared", "failed"]


class TestHeal:
    def test_incomplete_claims_beat_everything_including_dry_run(self):
        heals, reg, lookup = _run({"s": _audit()}, {"appdb": ["s", "o"]}, complete=False, dry_run=True)
        assert heals == [rr.HealResult("s", "appdb", "failed", "claims-unresolved")]
        reg.assert_not_called()
        lookup.assert_not_called()

    def test_shared_lists_all_other_claimants_sorted_and_deduplicated(self):
        claims = {"appdb": ["zeta", "s", "alpha", "alpha"]}
        heals, reg, _ = _run({"s": _audit()}, claims)
        assert heals == [rr.HealResult("s", "appdb", "shared", "alpha,zeta")]
        reg.assert_not_called()

    def test_shared_beats_dry_run(self):
        heals, _, _ = _run({"s": _audit()}, {"appdb": ["s", "o"]}, dry_run=True)
        assert heals[0].outcome == "shared"

    def test_own_duplicate_claim_is_not_shared(self):
        heals, _, _ = _run({"s": _audit()}, {"appdb": ["s", "s"]}, dry_run=True)
        assert heals[0].outcome == "would-register"

    def test_claims_for_another_database_do_not_make_it_shared(self):
        heals, _, _ = _run({"s": _audit()}, {"other_db": ["x"]}, dry_run=True)
        assert heals[0].outcome == "would-register"

    def test_database_absent_from_the_claim_map_is_not_shared(self):
        heals, _, _ = _run({"s": _audit()}, {}, dry_run=True)
        assert heals == [rr.HealResult("s", "appdb", "would-register", "")]

    def test_dry_run_never_validates_or_looks_up_the_owner(self):
        heals, reg, lookup = _run({"s": _audit("bad name;")}, {}, dry_run=True)
        assert heals[0].outcome == "would-register"
        lookup.assert_not_called()
        reg.assert_not_called()

    def test_register_called_with_owner_spec_and_dated_notes(self):
        heals, reg, lookup = _run({"s": _audit()}, {"appdb": ["s"]}, owner="role_x")
        assert heals == [rr.HealResult("s", "appdb", "registered")]
        lookup.assert_called_once_with("appdb", rr.POSTGRES_CONTAINER)
        (db,), kw = reg.call_args
        assert db == "appdb"
        assert kw["spec_id"] == "s" and kw["user"] == "role_x" and kw["owner"] == "fabrik"
        assert kw["notes"].startswith("registered by the hourly reconcile 20")
        assert len(kw["notes"].rsplit(" ", 1)[1]) == 10  # ISO date

    def test_write_returning_false_is_already_present(self):
        heals, _, _ = _run({"s": _audit()}, {"appdb": ["s"]}, wrote=False)
        assert heals[0].outcome == "already-present"
        assert heals[0].reason == ""

    def test_owner_none_is_owner_unresolved_without_write(self):
        heals, reg, _ = _run({"s": _audit()}, {"appdb": ["s"]}, owner=None)
        assert heals == [rr.HealResult("s", "appdb", "failed", "owner-unresolved")]
        reg.assert_not_called()

    def test_empty_string_owner_is_still_written(self):
        # Only None means unresolved; "" is passed through to the registry write.
        heals, reg, _ = _run({"s": _audit()}, {"appdb": ["s"]}, owner="")
        assert heals[0].outcome == "registered"
        assert reg.call_args.kwargs["user"] == ""

    @pytest.mark.parametrize("bad", ["has-hyphen", "semi;colon", "sp ace", "1leading"])
    def test_invalid_identifier_fails_with_its_exception_name(self, bad):
        heals, reg, lookup = _run({"s": _audit(bad)}, {bad: ["s"]})
        assert heals[0].outcome == "failed"
        assert heals[0].reason == "ValueError"
        lookup.assert_not_called()
        reg.assert_not_called()

    def test_owner_lookup_exception_becomes_failed_with_type_name(self):
        with (
            patch.object(rr, "_db_owner", side_effect=TimeoutError("slow")),
            patch.object(rr, "register_allocation_if_absent") as reg,
        ):
            heals = rr.reconcile_postgres(
                {"s": _audit()}, {"appdb": ["s"]}, claims_complete=True, dry_run=False
            )
        assert heals == [rr.HealResult("s", "appdb", "failed", "TimeoutError")]
        reg.assert_not_called()

    def test_one_failure_does_not_stop_later_candidates(self):
        calls = {"n": 0}

        def flaky(db, **_kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("disk")
            return True

        with (
            patch.object(rr, "_db_owner", return_value="o"),
            patch.object(rr, "register_allocation_if_absent", side_effect=flaky),
        ):
            heals = rr.reconcile_postgres(
                {"a": _audit("d1"), "b": _audit("d2")},
                {"d1": ["a"], "d2": ["b"]},
                claims_complete=True,
                dry_run=False,
            )
        assert [(h.outcome, h.reason) for h in heals] == [("failed", "OSError"), ("registered", "")]

    def test_base_exception_is_not_swallowed(self):
        with (
            patch.object(rr, "_db_owner", side_effect=KeyboardInterrupt),
            pytest.raises(KeyboardInterrupt),
        ):
            rr.reconcile_postgres(
                {"s": _audit()}, {"appdb": ["s"]}, claims_complete=True, dry_run=False
            )


class TestLogging:
    def test_each_outcome_is_logged_with_spec_db_and_outcome(self, caplog):
        with caplog.at_level(logging.INFO, logger=rr.logger.name):
            _run({"s": _audit()}, {"appdb": ["s"]})
        msgs = [r.getMessage() for r in caplog.records]
        assert msgs == ["registry reconcile: spec=s db=appdb outcome=registered"]

    def test_reason_is_appended_when_present(self, caplog):
        with caplog.at_level(logging.INFO, logger=rr.logger.name):
            _run({"s": _audit()}, {"appdb": ["s", "o"]})
        assert caplog.records[0].getMessage().endswith("outcome=shared reason=o")

    def test_skipped_audits_log_nothing(self, caplog):
        with caplog.at_level(logging.INFO, logger=rr.logger.name):
            _run({"s": _audit(status="present")})
        assert caplog.records == []
