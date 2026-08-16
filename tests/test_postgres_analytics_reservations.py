"""The cost-budget RESERVATION lane in ``ensure_shared_analytics_db``.

Provisioned centrally at fabrik-lib's request (fabrik-mail ``01M00SRW2Y4AYNAYP6G928TZ0A``) because
host projects do not apply schema files themselves — the same contract ``cost_ledger`` already runs
under (``infrastructure.py:454-458``).

All VPS mutations are mocked at the ``ssh`` boundary; nothing here talks to the live cluster.

⚠️ The function had **no test at all** before this file, despite being called on every
``fabrik apply`` (``infrastructure.py:476``). The two behaviours that most needed pinning are the
ones a reviewer cannot see by reading the diff:

* **fail-soft** — an unreadable fabrik-lib path must NOT break ``fabrik apply`` for the ~46
  projects that have no reservation lane, while ``cost_ledger`` stays fatal-on-missing because it
  is load-bearing for every deploy. Getting that asymmetry backwards is a fleet-wide outage.
* **the GRANT divergence** — ``cost_ledger`` must stay append-only. A regression that widened it to
  UPDATE would be invisible in review (one word in an f-string) and would let a project role
  rewrite accounting history.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from fabrik.drivers import postgres as pg

ROLE = "proj_role"


def _schema(tmp_path):
    """A stand-in for fabrik-lib's reservation DDL — content is irrelevant, delivery is not."""
    p = tmp_path / "schema_reservations_pg.sql"
    p.write_text(
        "CREATE TABLE IF NOT EXISTS cost_reservations (job_id uuid PRIMARY KEY);\n"
        "ALTER TABLE cost_reservations ENABLE ROW LEVEL SECURITY;\n",
        encoding="utf-8",
    )
    return p


def _ledger(tmp_path):
    p = tmp_path / "schema_pg.sql"
    p.write_text("CREATE TABLE IF NOT EXISTS cost_ledger (id bigint);\n", encoding="utf-8")
    return p


@pytest.fixture
def run(tmp_path):
    """Invoke the registrar with every outbound call captured, DB reported as already existing."""

    def _invoke(**kw):
        calls: list[str] = []
        with (
            patch.object(pg, "ssh", side_effect=lambda cmd, *a, **k: calls.append(cmd)),
            patch.object(pg, "_run_sql", return_value="1"),
            patch.object(pg, "_read_subagent_runs_ddl", return_value="SELECT 1;"),
        ):
            kw.setdefault("schema_path", str(_ledger(tmp_path)))
            kw.setdefault("reservations_schema_path", str(_schema(tmp_path)))
            result = pg.ensure_shared_analytics_db(**kw)
        return result, calls

    return _invoke


def test_reservation_ddl_is_applied_and_reported(run):
    result, calls = run()
    assert result["reservations_applied"] is True, "the lane was not provisioned"
    assert result["schema_applied"] is True, "cost_ledger must still be applied alongside it"
    assert any("base64 -d" in c and pg.FABRIK_ANALYTICS_DB in c for c in calls)


def test_reservation_ddl_uses_on_error_stop(run):
    """The DDL carries RLS policies; psql's default continue-on-error is the dangerous outcome.

    Without ON_ERROR_STOP a run can create the TABLE, skip the POLICY, and still exit 0 — a table
    that looks provisioned and is not isolated.
    """
    _, calls = run()
    assert any("ON_ERROR_STOP=1" in c for c in calls), (
        "reservation DDL piped without ON_ERROR_STOP — a failed CREATE POLICY would pass silently"
    )


def test_a_missing_fabrik_lib_path_is_fail_soft(run, tmp_path):
    """The whole point of the asymmetry: a missing reservation file must not break `fabrik apply`."""
    result, calls = run(reservations_schema_path=str(tmp_path / "does-not-exist.sql"))
    assert result["reservations_applied"] is False, "must report the skip, not claim success"
    assert result["schema_applied"] is True, "cost_ledger must still be applied — it is unrelated"
    assert calls, "the run aborted entirely instead of continuing past the missing optional file"


def test_cost_ledger_stays_append_only_when_the_role_is_granted(run):
    """A role that can UPDATE cost_ledger can rewrite accounting history. It must never be granted."""
    _, calls = run(grant_to_role=ROLE)
    grants = [c for c in calls if "GRANT" in c or "R1JBTlQ" in c]
    assert grants, "no GRANT was issued at all"
    import base64

    decoded = "\n".join(
        base64.b64decode(c.split("echo ")[1].split(" |")[0]).decode(errors="replace")
        for c in calls
        if "echo " in c and "base64 -d" in c
    )
    ledger_lines = [ln for ln in decoded.splitlines() if "cost_ledger" in ln and "GRANT" in ln]
    assert ledger_lines, "no GRANT on cost_ledger found"
    for ln in ledger_lines:
        assert "UPDATE" not in ln.upper(), f"cost_ledger granted UPDATE — history becomes rewritable: {ln}"
        assert "DELETE" not in ln.upper(), f"cost_ledger granted DELETE: {ln}"


def test_the_reservation_tables_do_get_update(run):
    """Settle/reclaim mutate a reservation in place; without UPDATE the lane cannot function."""
    import base64

    _, calls = run(grant_to_role=ROLE)
    decoded = "\n".join(
        base64.b64decode(c.split("echo ")[1].split(" |")[0]).decode(errors="replace")
        for c in calls
        if "echo " in c and "base64 -d" in c
    )
    for table in ("cost_reservations", "cost_budget_month_totals"):
        line = [ln for ln in decoded.splitlines() if "GRANT" in ln and table in ln]
        assert line, f"no GRANT issued for {table}"
        assert "UPDATE" in line[0].upper(), f"{table} needs UPDATE to settle/reclaim: {line[0]}"


def test_no_reservation_grant_when_the_lane_was_not_applied(run, tmp_path):
    """Granting on a table the run just failed to create would error the whole GRANT batch."""
    import base64

    _, calls = run(
        grant_to_role=ROLE, reservations_schema_path=str(tmp_path / "missing.sql")
    )
    decoded = "\n".join(
        base64.b64decode(c.split("echo ")[1].split(" |")[0]).decode(errors="replace")
        for c in calls
        if "echo " in c and "base64 -d" in c
    )
    assert "cost_reservations" not in decoded or "GRANT" not in decoded.split("cost_reservations")[0][-80:], (
        "granted on cost_reservations although the DDL was skipped — the batch would fail"
    )


def test_dry_run_touches_nothing(run):
    result, calls = run(dry_run=True)
    assert result["status"] == "dry_run"
    assert result["reservations_applied"] is False
    assert not calls, "dry_run issued real ssh calls"
