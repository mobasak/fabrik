"""A spec that names a store in ``depends:`` while its shape flag is off is SAID, not silent (W-81524f52).

The registrar keys only on the shape flag, so ``depends.postgres: trading`` beside
``needs_database: false`` (or no ``shape:`` block, where the python-api default is false)
provisions nothing. The printed reason used to read "not applicable: shape.needs_database=false"
— indistinguishable from a considered choice — and at ``fabrik apply`` even that line was logged
at INFO, which no CLI handler shows. The bool is unchanged; the reason carries a diagnostic
clause and ``provision()`` logs it at WARNING.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fabrik.orchestrator import DeploymentContext
from fabrik.orchestrator.infrastructure import (
    InfrastructureProvisioner,
    format_resolved_summary,
    resolve_applicability,
)
from fabrik.spec_loader import load_spec

_PLAIN_PG = "not applicable: shape.needs_database=false"
_PLAIN_REDIS = "not applicable: shape.needs_cache=false"


def _spec(shape: dict, depends: object = None) -> dict:
    spec: dict = {"id": "demo", "shape": {"kind": "service", **shape}}
    if depends is not None:
        spec["depends"] = depends
    return spec


@pytest.mark.parametrize(
    "depends", [{"postgres": "trading"}, {"postgres_seed": "backups/seed.sql.gz"}]
)
def test_named_postgres_dependency_without_the_flag_is_said(depends: dict) -> None:
    should_run, reason = resolve_applicability(_spec({"needs_database": False}, depends))[
        "postgres"
    ]
    value = next(iter(depends.values()))
    assert should_run is False
    assert reason.startswith(_PLAIN_PG)
    assert f"={value}" in reason
    assert "will NOT create" in reason
    assert "(" not in reason, "the summary wraps the reason in parens; no nested ones"


def test_named_redis_dependency_without_the_flag_is_said() -> None:
    should_run, reason = resolve_applicability(_spec({"needs_cache": False}, {"redis": "main"}))[
        "redis"
    ]
    assert should_run is False
    assert reason.startswith(_PLAIN_REDIS)
    assert "depends.redis=main" in reason
    assert "will NOT create" in reason


@pytest.mark.parametrize(
    "depends",
    [
        None,
        {},
        {"postgres": None, "redis": None, "postgres_seed": None},
        {"postgres": "", "redis": ""},
        {"postgres": "  \n\t", "redis": " "},
        "not-a-mapping",
    ],
)
def test_no_named_dependency_keeps_the_plain_reason(depends: object) -> None:
    resolved = resolve_applicability(_spec({}, depends))
    assert resolved["postgres"] == (False, _PLAIN_PG)
    assert resolved["redis"] == (False, _PLAIN_REDIS)


def test_flag_true_with_depends_is_unchanged() -> None:
    resolved = resolve_applicability(
        _spec(
            {"needs_database": True, "needs_cache": True}, {"postgres": "trading", "redis": "main"}
        )
    )
    assert resolved["postgres"] == (True, "shape.needs_database=true")
    assert resolved["redis"] == (True, "shape.needs_cache=true")


class _StopError(Exception):
    """Raised at the first side-effecting step, so the test sees only the summary."""


def _provision_until_first_side_effect(spec: dict) -> None:
    ctx = DeploymentContext(spec_path=Path("/tmp/unused.yaml"))
    ctx.spec = spec
    ctx.dry_run = True
    prov = InfrastructureProvisioner(deployer=MagicMock())
    with (
        patch.object(
            InfrastructureProvisioner, "_provision_shared_analytics", side_effect=_StopError
        ),
        pytest.raises(_StopError),
    ):
        prov.provision(ctx)


def test_apply_logs_the_contradiction_at_warning(caplog: pytest.LogCaptureFixture) -> None:
    """INFO is invisible at ``fabrik apply`` (no handler); WARNING reaches stderr."""
    caplog.set_level(logging.DEBUG, logger="fabrik.orchestrator.infrastructure")
    _provision_until_first_side_effect(_spec({"needs_database": False}, {"postgres": "trading"}))
    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any(
        m.startswith("postgres registrar skipped for demo: depends.postgres=trading ")
        for m in warnings
    ), warnings


def test_apply_logs_no_warning_for_a_clean_spec(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="fabrik.orchestrator.infrastructure")
    _provision_until_first_side_effect(_spec({"needs_database": True}, {"postgres": "trading"}))
    assert not [
        r for r in caplog.records if r.levelno >= logging.WARNING and "depends." in r.getMessage()
    ]


def test_legacy_spec_without_shape_block_carries_the_clause(tmp_path: Path) -> None:
    # No shape: block — the template-defaults merge gives python-api needs_database=false.
    spec_file = tmp_path / "legacy.yaml"
    spec_file.write_text(
        "id: legacy-demo\nkind: service\ntemplate: python-api\ndomain: legacy.example.com\n"
        "source:\n  type: local\n  path: /opt/legacy-demo\n"
        "depends:\n  postgres: legacy\n"
    )
    spec = load_spec(spec_file)
    assert spec.shape is not None and spec.shape.needs_database is False
    summary = format_resolved_summary(resolve_applicability(spec.model_dump(mode="python")))
    pg_line = next(line for line in summary.splitlines() if line.strip().startswith("postgres"))
    assert "skipped" in pg_line
    assert "depends.postgres=legacy" in pg_line


def test_a_multiline_value_stays_on_one_summary_line() -> None:
    """A raw-YAML value with a newline must not split the one-line summary or the log record."""
    resolved = resolve_applicability(_spec({}, {"postgres": "legacy\n  db"}))
    reason = resolved["postgres"][1]
    assert "depends.postgres=legacy db " in reason
    assert "\n" not in reason
    # The summary's postgres row must hold the whole clause: a split value would leave the
    # tail of the clause on a line of its own.
    rows = format_resolved_summary(resolved).splitlines()
    pg_rows = [row for row in rows if row.strip().startswith("postgres")]
    assert len(pg_rows) == 1 and "legacy db names a store" in pg_rows[0], rows
    assert not [row for row in rows if "names a store" in row and row not in pg_rows], rows
