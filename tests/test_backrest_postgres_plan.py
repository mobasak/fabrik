"""Phase 6 of deploy-readiness-gaps: per-DB Backrest plan registration.

Each fabrik-created database gets its own Backrest plan with per-DB
retention, layered on top of the existing whole-cluster pg_dumpall.

Per docs/development/plans/2026-06-30-plan-fabrik-deploy-readiness-gaps.md
Phase 6. All VPS-side mutations (add_backup_plan, run_locked, ssh) are
mocked — this suite is hermetic.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from fabrik.drivers import backrest, postgres


# ---------------------------------------------------------------------------
# register_postgres_plan
# ---------------------------------------------------------------------------
class TestRegisterPostgresPlan:
    def test_register_calls_add_backup_plan_with_per_db_id_and_path(self) -> None:
        with (
            patch("fabrik.drivers.backrest.add_backup_plan") as mock_add,
            patch("fabrik.drivers.backrest._append_tracked_db") as mock_track,
        ):
            mock_add.return_value = {"status": "created", "plan": "postgres-calendar_engine"}
            result = backrest.register_postgres_plan("calendar_engine")

        assert result["status"] == "created"
        mock_add.assert_called_once()
        kw = mock_add.call_args.kwargs
        assert kw["plan_id"] == "postgres-calendar_engine"
        assert kw["paths"] == ["/opt/backups/postgres/calendar_engine/"]
        # Plan inherits the postgres-dumps schedule + retention defaults
        assert kw["schedule_cron"] == "0 2 * * *"
        mock_track.assert_called_once_with("calendar_engine")

    def test_register_idempotent_when_plan_exists(self) -> None:
        with (
            patch("fabrik.drivers.backrest.add_backup_plan") as mock_add,
            patch("fabrik.drivers.backrest._append_tracked_db"),
        ):
            mock_add.return_value = {"status": "exists", "plan": "postgres-foo"}
            result = backrest.register_postgres_plan("foo")
        assert result["status"] == "exists"

    def test_register_rejects_invalid_db_name(self) -> None:
        """Pass-2 adversarial: shell-special character could break the
        pre-backup.sh for-loop on the VPS. Must validate before append."""
        for bad in ["foo;rm -rf /", "foo bar", "foo`whoami`", "foo$x", "", "1foo", "-foo"]:
            with pytest.raises(ValueError):
                backrest.register_postgres_plan(bad)

    def test_register_accepts_valid_db_name(self) -> None:
        with (
            patch("fabrik.drivers.backrest.add_backup_plan") as mock_add,
            patch("fabrik.drivers.backrest._append_tracked_db"),
        ):
            mock_add.return_value = {"status": "created", "plan": "postgres-foo_bar123"}
            backrest.register_postgres_plan("foo_bar123")  # alnum + underscore OK


# ---------------------------------------------------------------------------
# unregister_postgres_plan
# ---------------------------------------------------------------------------
class TestUnregisterPostgresPlan:
    def test_unregister_calls_remove_and_removes_from_tracked_file(self) -> None:
        with (
            patch("fabrik.drivers.backrest.remove_backup_plan") as mock_remove,
            patch("fabrik.drivers.backrest._remove_tracked_db") as mock_untrack,
        ):
            mock_remove.return_value = True
            result = backrest.unregister_postgres_plan("calendar_engine")
        assert result is True
        mock_remove.assert_called_once_with("postgres-calendar_engine", dry_run=False)
        mock_untrack.assert_called_once_with("calendar_engine")

    def test_unregister_continues_even_when_remove_fails(self) -> None:
        """remove_backup_plan returns False on lock/script failure. The
        tracked-DBs file scrub must still run so the next register attempt
        for the same name doesn't double-append."""
        with (
            patch("fabrik.drivers.backrest.remove_backup_plan") as mock_remove,
            patch("fabrik.drivers.backrest._remove_tracked_db") as mock_untrack,
        ):
            mock_remove.return_value = False
            result = backrest.unregister_postgres_plan("calendar_engine")
        assert result is False
        mock_untrack.assert_called_once_with("calendar_engine")


# ---------------------------------------------------------------------------
# _append_tracked_db — idempotent file append via SSH
# ---------------------------------------------------------------------------
class TestAppendTrackedDb:
    def test_append_writes_to_tracked_file_via_ssh(self) -> None:
        with patch("fabrik.drivers.backrest.ssh") as mock_ssh:
            backrest._append_tracked_db("calendar_engine")
        mock_ssh.assert_called_once()
        cmd = mock_ssh.call_args.args[0]
        # Must reference the tracked-dbs file path
        assert "/opt/backups/fabrik-tracked-dbs.txt" in cmd
        # Must use idempotent pattern (grep -qx + echo) — not raw append
        assert "grep" in cmd and "calendar_engine" in cmd

    def test_append_validates_db_name(self) -> None:
        for bad in ["foo;ls", "$x", "", "1foo"]:
            with pytest.raises(ValueError):
                backrest._append_tracked_db(bad)


class TestRemoveTrackedDb:
    def test_remove_uses_sed_to_strip_line(self) -> None:
        with patch("fabrik.drivers.backrest.ssh") as mock_ssh:
            backrest._remove_tracked_db("calendar_engine")
        mock_ssh.assert_called_once()
        cmd = mock_ssh.call_args.args[0]
        assert "calendar_engine" in cmd
        assert "fabrik-tracked-dbs.txt" in cmd

    def test_remove_validates_db_name(self) -> None:
        for bad in ["foo;ls", "$x", "", "1foo"]:
            with pytest.raises(ValueError):
                backrest._remove_tracked_db(bad)


# ---------------------------------------------------------------------------
# Integration: create_database / drop_database call into backrest registrar
# ---------------------------------------------------------------------------
class TestPostgresIntegration:
    def test_create_database_calls_register_postgres_plan(self) -> None:
        """After role+grant succeed in create_database(), the new per-DB
        backup plan must be registered."""
        with (
            patch("fabrik.drivers.postgres._run_sql"),
            patch("fabrik.drivers.postgres.database_exists", return_value=False),
            patch("fabrik.drivers.postgres.register_allocation"),
            patch("fabrik.drivers.postgres.register_postgres_plan") as mock_register,
        ):
            postgres.create_database("calendar_engine", db_user="calendar_user")
        mock_register.assert_called_once_with("calendar_engine")

    def test_create_database_skips_register_on_dry_run(self) -> None:
        with patch("fabrik.drivers.postgres.register_postgres_plan") as mock_register:
            postgres.create_database("calendar_engine", db_user="calendar_user", dry_run=True)
        mock_register.assert_not_called()

    def test_create_database_skips_register_on_existing_db(self) -> None:
        """If the DB already exists (inline SELECT returns '1'), create_database
        returns early with status='exists' and does NOT touch the per-DB plan.
        Re-registering on every re-apply would just churn SSH calls."""
        # Inline check uses _run_sql with `SELECT 1 FROM pg_database`; return "1"
        with (
            patch("fabrik.drivers.postgres._run_sql", return_value="1\n"),
            patch("fabrik.drivers.postgres.register_postgres_plan") as mock_register,
        ):
            result = postgres.create_database("calendar_engine", db_user=None)
        assert result["status"] == "exists"
        mock_register.assert_not_called()

    def test_create_database_continues_when_register_fails(self) -> None:
        """register_postgres_plan failure must not crash create_database —
        the DB+role exist, the per-DB plan is a nice-to-have that the
        operator can register manually."""
        with (
            patch("fabrik.drivers.postgres._run_sql"),
            patch("fabrik.drivers.postgres.database_exists", return_value=False),
            patch("fabrik.drivers.postgres.register_allocation"),
            patch(
                "fabrik.drivers.postgres.register_postgres_plan",
                side_effect=RuntimeError("backrest down"),
            ),
        ):
            # Should NOT raise
            result = postgres.create_database("calendar_engine", db_user="calendar_user")
        assert result["status"] == "created"

    def test_drop_database_calls_unregister(self) -> None:
        # drop_database does its own inline SELECT 1 via _run_sql; return "1" to
        # signal DB exists so the drop path proceeds (not the not-found branch).
        with (
            patch("fabrik.drivers.postgres._run_sql", return_value="1\n"),
            patch("fabrik.drivers.postgres.unregister_allocation"),
            patch("fabrik.drivers.postgres.unregister_postgres_plan") as mock_unreg,
        ):
            postgres.drop_database("calendar_engine")
        mock_unreg.assert_called_once_with("calendar_engine")
