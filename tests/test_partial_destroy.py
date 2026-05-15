"""Tests for ``fabrik destroy --partial`` + HANDLER_ARGS/HANDLER_FUNCS export contract.

T2-02 G-F5. T4-02 depends on these constants being importable at module
level — these tests are the regression net for that contract.
"""

from __future__ import annotations

import inspect
from unittest.mock import patch

import pytest


def test_module_level_import_succeeds():
    """HANDLER_ARGS + HANDLER_FUNCS must be at module level (T4-02 dependency).

    A function-local definition would make this import raise ImportError
    or AttributeError. The test runs at module collection time.
    """
    from fabrik.orchestrator.destroyer import HANDLER_ARGS, HANDLER_FUNCS
    assert isinstance(HANDLER_ARGS, dict)
    assert isinstance(HANDLER_FUNCS, dict)


def test_handler_keys_exactly_8_destroy_handlers():
    """The 8 destroy-handler registrars; grafana intentionally excluded."""
    from fabrik.orchestrator.destroyer import HANDLER_ARGS, HANDLER_FUNCS
    expected = {
        "postgres", "redis", "gatus", "backrest", "glitchtip",
        "authelia", "meilisearch", "prometheus",
    }
    assert set(HANDLER_ARGS) == expected
    assert set(HANDLER_FUNCS) == expected


def test_grafana_intentionally_excluded():
    """Grafana annotations are decorative; not destroyable."""
    from fabrik.orchestrator.destroyer import HANDLER_ARGS, HANDLER_FUNCS
    assert "grafana" not in HANDLER_ARGS
    assert "grafana" not in HANDLER_FUNCS


def test_handler_args_keys_equal_handler_funcs_keys():
    from fabrik.orchestrator.destroyer import HANDLER_ARGS, HANDLER_FUNCS
    assert set(HANDLER_ARGS) == set(HANDLER_FUNCS)


def test_handler_args_signatures_match_destroy_functions():
    """Each lambda's output tuple must have the right arity for its func."""
    from fabrik.orchestrator.destroyer import HANDLER_ARGS, HANDLER_FUNCS

    class FakeSpec:
        id = "test-svc"
        domain = "test.example.com"

    fake_spec = FakeSpec()
    for name, arg_builder in HANDLER_ARGS.items():
        args_tuple = arg_builder(fake_spec, True, False)
        fn = HANDLER_FUNCS[name]
        sig = inspect.signature(fn)
        required_params = [
            p for p in sig.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind != inspect.Parameter.VAR_POSITIONAL
            and p.kind != inspect.Parameter.VAR_KEYWORD
        ]
        assert len(args_tuple) == len(required_params), (
            f"{name}: lambda returns {len(args_tuple)} args "
            f"but {fn.__name__} requires {len(required_params)}"
        )


def test_authelia_lambda_uses_domain_not_id():
    """authelia's _destroy signature is (domain, dry_run) — not (name, ...)."""
    from fabrik.orchestrator.destroyer import HANDLER_ARGS

    class FakeSpec:
        id = "wrong-value"
        domain = "expected.example.com"

    args = HANDLER_ARGS["authelia"](FakeSpec(), False, True)
    assert args[0] == "expected.example.com"
    assert args[1] is True  # dry_run


def test_postgres_lambda_includes_drop_data():
    """postgres + redis + meilisearch get drop_data; others don't."""
    from fabrik.orchestrator.destroyer import HANDLER_ARGS

    class FakeSpec:
        id = "svc"
        domain = "x.example.com"

    spec = FakeSpec()
    # Data-bearing registrars get drop_data in args
    for reg in ("postgres", "redis", "meilisearch"):
        args = HANDLER_ARGS[reg](spec, True, False)
        assert len(args) == 3
        assert args[1] is True  # drop_data
        assert args[2] is False  # dry_run

    # Non-data-bearing registrars get (id|domain, dry_run)
    for reg in ("gatus", "backrest", "glitchtip", "prometheus"):
        args = HANDLER_ARGS[reg](spec, True, False)
        assert len(args) == 2
        assert args[1] is False  # dry_run


# ─────────────────────────────────────────────────────────────────────────────
# CLI integration: fabrik destroy --partial
# ─────────────────────────────────────────────────────────────────────────────


class TestPartialDestroyCLI:
    """End-to-end CLI tests using click's CliRunner."""

    def _runner(self):
        from click.testing import CliRunner

        return CliRunner()

    def _make_spec(self, tmp_path):
        spec_path = tmp_path / "test.yaml"
        spec_path.write_text(
            "id: test-svc\n"
            "kind: service\n"
            "template: python-api\n"
            "domain: test.example.com\n"
            "shape:\n"
            "  is_public: true\n"
            "  is_admin_dashboard: true\n"
        )
        return spec_path

    def test_partial_dispatches_only_named_registrars(self, tmp_path, monkeypatch):
        # monkeypatch.setitem auto-restores at teardown — prevents
        # cross-test HANDLER_FUNCS pollution that would otherwise leak.
        spec_path = self._make_spec(tmp_path)
        from fabrik.cli import cli
        from fabrik.orchestrator.destroyer import ActionResult, HANDLER_FUNCS

        calls: list[str] = []

        def make_mock(name):
            def fn(*args, **kwargs):
                calls.append(name)
                return ActionResult(name, "dry_run", detail=f"mocked {name}")
            return fn

        monkeypatch.setitem(HANDLER_FUNCS, "gatus", make_mock("gatus"))
        monkeypatch.setitem(HANDLER_FUNCS, "backrest", make_mock("backrest"))

        result = self._runner().invoke(
            cli,
            ["destroy", str(spec_path), "--partial", "gatus",
             "--partial", "backrest", "--dry-run"],
        )

        assert result.exit_code == 0, result.output
        assert "gatus" in result.output
        assert "backrest" in result.output
        assert sorted(calls) == ["backrest", "gatus"]

    def test_partial_with_unknown_registrar_exits_1(self, tmp_path):
        spec_path = self._make_spec(tmp_path)
        from fabrik.cli import cli

        result = self._runner().invoke(
            cli,
            ["destroy", str(spec_path), "--partial", "nonexistent",
             "--dry-run"],
        )
        assert result.exit_code == 1
        assert "unknown registrar" in result.output

    def test_partial_with_valid_plus_unknown_still_exits_1(self, tmp_path, monkeypatch):
        spec_path = self._make_spec(tmp_path)
        from fabrik.cli import cli
        from fabrik.orchestrator.destroyer import ActionResult, HANDLER_FUNCS

        monkeypatch.setitem(
            HANDLER_FUNCS, "gatus", lambda *a, **k: ActionResult("gatus", "dry_run")
        )

        result = self._runner().invoke(
            cli,
            ["destroy", str(spec_path),
             "--partial", "gatus", "--partial", "nonexistent",
             "--dry-run"],
        )
        # gatus succeeded but nonexistent failed → exit 1
        assert result.exit_code == 1
        assert "gatus" in result.output
        assert "unknown registrar" in result.output

    def test_handler_funcs_restored_after_monkeypatch(self):
        """Sanity: after monkeypatch teardown, HANDLER_FUNCS["gatus"] is
        the real `_destroy_gatus` again — proves F1 fix works."""
        from fabrik.orchestrator.destroyer import _destroy_gatus, HANDLER_FUNCS
        assert HANDLER_FUNCS["gatus"] is _destroy_gatus
