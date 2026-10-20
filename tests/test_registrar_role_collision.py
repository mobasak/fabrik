"""The registrar's foreign-role guard, unit level (W-f599a88c; the behaviour on real PostgreSQL is in
tests/test_registrar_role_collision_real_pg.py).

The guard must fail CLOSED (a query that errors or answers without its end marker raises, never reads as
"no reasons") and must run before anything is created, so a mixed absent/foreign pair never orphans a
freshly minted sibling's one-time password.
"""

from __future__ import annotations

from unittest import mock

import pytest

import fabrik.drivers.postgres as pg


def test_the_guard_query_runs_under_on_error_stop_and_returns_its_reasons() -> None:
    with mock.patch.object(pg, "_run_sql", return_value="owns database x_wd_rw\n__end__") as run:
        assert pg._foreign_role_reasons("x_wd_rw", own_db="x") == ["owns database x_wd_rw"]
    sql = run.call_args.args[0]
    assert sql.startswith("\\set ON_ERROR_STOP on\n")
    assert "pg_shdepend" in sql and "datdba" in sql


@pytest.mark.parametrize(
    "out", ["", "owns database x", "garbage"], ids=["empty", "no-marker", "noise"]
)
def test_an_answer_without_its_end_marker_raises_never_reads_clean(out: str) -> None:
    with (
        mock.patch.object(pg, "_run_sql", return_value=out),
        pytest.raises(RuntimeError, match="guard"),
    ):
        pg._foreign_role_reasons("x_wd_rw", own_db="x")


def test_the_create_database_form_also_counts_grants_and_memberships() -> None:
    with mock.patch.object(pg, "_run_sql", return_value="__end__") as run:
        pg._foreign_role_reasons("x_wd_ro", own_db=None, any_dependency=True)
    sql = run.call_args.args[0]
    assert "pg_auth_members" in sql and "deptype <> 'o'" in sql


def test_the_watchdog_checks_both_roles_before_creating_either() -> None:
    calls: list[str] = []

    def run_sql(sql, **k):
        calls.append(sql)
        return ""

    def reasons(role, **k):
        return ["owns database x_wd_rw"] if role.endswith("_wd_rw") else []

    with (
        mock.patch.object(pg, "_role_exists", side_effect=lambda r, c: r.endswith("_wd_rw")),
        mock.patch.object(pg, "_foreign_role_reasons", side_effect=reasons),
        mock.patch.object(pg, "_db_owner", return_value="x"),
        mock.patch.object(pg, "_run_sql", side_effect=run_sql),
        pytest.raises(RuntimeError, match="not this registrar's"),
    ):
        pg.create_watchdog_roles("x")
    assert calls == []  # the absent RO sibling was never created, nothing was granted


def test_the_subagent_role_checks_before_any_grant() -> None:
    with (
        mock.patch.object(pg, "_role_exists", return_value=True),
        mock.patch.object(
            pg, "_foreign_role_reasons", return_value=["owns database x_subagent_ins"]
        ),
        mock.patch.object(pg, "_run_sql") as run,
        pytest.raises(RuntimeError, match="not this registrar's"),
    ):
        pg.create_subagent_ins_role("x")
    run.assert_not_called()


def test_create_database_checks_an_existing_role_before_creating_the_database() -> None:
    calls: list[str] = []
    with (
        mock.patch.object(pg, "_run_sql", side_effect=lambda sql, **k: calls.append(sql) or ""),
        mock.patch.object(pg, "_role_exists", return_value=True),
        mock.patch.object(
            pg, "_foreign_role_reasons", return_value=["is a member of x_wd_ro"]
        ) as g,
        pytest.raises(RuntimeError, match="not this registrar's"),
    ):
        pg.create_database("x_wd_ro", "x_wd_ro")
    assert g.call_args.kwargs == {"own_db": None, "any_dependency": True, "container": mock.ANY}
    assert not any("CREATE DATABASE" in c for c in calls)


def test_the_message_names_the_real_fix_never_drop_or_re_own() -> None:
    with (
        mock.patch.object(pg, "_role_exists", return_value=True),
        mock.patch.object(
            pg, "_foreign_role_reasons", return_value=["owns database x_subagent_ins"]
        ),
        mock.patch.object(pg, "_run_sql"),
        pytest.raises(RuntimeError) as err,
    ):
        pg.create_subagent_ins_role("x")
    text = str(err.value)
    assert "depends.postgres" in text
    assert "DROP ROLE" not in text and "OWNER TO" not in text
