"""Phase 5 of deploy-readiness-gaps: DB seed auto-restore.

Tests the new `_count_user_tables` + `_restore_seed` helpers and the
`postgres_seed` integration in `create_database`. All VPS-side mutations
(scp + docker exec) are mocked — this suite is hermetic.

Per docs/development/plans/2026-06-30-plan-fabrik-deploy-readiness-gaps.md
Phase 5.
"""

from __future__ import annotations

import gzip
from pathlib import Path
from unittest.mock import patch

import pytest

from fabrik.drivers import postgres


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------
class TestSeedPathValidation:
    """Per the plan §"Security": validate against directory traversal +
    absolute paths. The spec_dir prefix MUST be honored."""

    def test_resolve_rejects_absolute_path(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / "myspec"
        spec_dir.mkdir()
        with pytest.raises(ValueError, match="absolute"):
            postgres._resolve_seed_path(spec_dir, "/etc/passwd")

    def test_resolve_rejects_parent_escape(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / "myspec"
        spec_dir.mkdir()
        with pytest.raises(ValueError, match="outside"):
            postgres._resolve_seed_path(spec_dir, "../../../etc/passwd")

    def test_resolve_rejects_mixed_escape(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / "myspec"
        (spec_dir / "backups").mkdir(parents=True)
        with pytest.raises(ValueError, match="outside"):
            postgres._resolve_seed_path(spec_dir, "backups/../../../etc/passwd")

    def test_resolve_accepts_relative_inside_spec(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / "myspec"
        (spec_dir / "backups").mkdir(parents=True)
        seed = spec_dir / "backups" / "calendar_engine_seed.sql.gz"
        seed.write_bytes(b"\x1f\x8b\x08\x00")  # gzip magic bytes
        resolved = postgres._resolve_seed_path(spec_dir, "backups/calendar_engine_seed.sql.gz")
        assert resolved == seed

    def test_resolve_rejects_missing_file(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / "myspec"
        spec_dir.mkdir()
        with pytest.raises(FileNotFoundError):
            postgres._resolve_seed_path(spec_dir, "backups/missing.sql.gz")

    def test_resolve_rejects_non_gzip_extension(self, tmp_path: Path) -> None:
        """Plan §Approach validator: `must end in .sql.gz`."""
        spec_dir = tmp_path / "myspec"
        (spec_dir / "backups").mkdir(parents=True)
        wrong = spec_dir / "backups" / "raw.sql"
        wrong.write_text("CREATE TABLE x();")
        with pytest.raises(ValueError, match=r"\.sql\.gz"):
            postgres._resolve_seed_path(spec_dir, "backups/raw.sql")


# ---------------------------------------------------------------------------
# _count_user_tables — adversarial-review-style: must filter pg_catalog
# ---------------------------------------------------------------------------
class TestCountUserTables:
    """The plan §"Approach" CORRECTED query excludes pg_catalog +
    information_schema. Pre-fix risk: pg_stat_statements extension would
    false-positive the idempotency guard."""

    def test_count_uses_information_schema_with_pg_catalog_exclusion(self) -> None:
        with patch("fabrik.drivers.postgres._run_sql") as mock_run:
            mock_run.return_value = "0\n"
            n = postgres._count_user_tables("postgres-main", "calendar_user", "calendar_engine")
        assert n == 0
        # The SQL must explicitly exclude pg_catalog + information_schema —
        # otherwise pg_stat_statements would false-positive on a fresh DB.
        sent_sql = mock_run.call_args[0][0]
        assert "information_schema.tables" in sent_sql
        assert "pg_catalog" in sent_sql
        assert "information_schema" in sent_sql
        assert "calendar_engine" in sent_sql

    def test_count_parses_int_from_psql_output(self) -> None:
        with patch("fabrik.drivers.postgres._run_sql") as mock_run:
            mock_run.return_value = "   42\n  "
            n = postgres._count_user_tables("postgres-main", "u", "db")
        assert n == 42

    def test_count_returns_zero_on_unparseable_output(self) -> None:
        """Defensive: a transient psql error shouldn't crash; treat as 0
        (the worst that can happen is a re-restore attempt, but the
        downstream restore call is itself idempotent at the SQL level
        — `psql` will error if tables already exist)."""
        with patch("fabrik.drivers.postgres._run_sql") as mock_run:
            mock_run.return_value = "ERROR: connection refused\n"
            n = postgres._count_user_tables("postgres-main", "u", "db")
        assert n == 0


# ---------------------------------------------------------------------------
# _restore_seed — orchestrate scp + docker exec + cleanup
# ---------------------------------------------------------------------------
class TestRestoreSeed:
    @pytest.fixture
    def fake_seed(self, tmp_path: Path) -> tuple[Path, Path]:
        spec_dir = tmp_path / "myspec"
        (spec_dir / "backups").mkdir(parents=True)
        seed = spec_dir / "backups" / "calendar_engine_seed.sql.gz"
        # Write a tiny valid gzip
        with gzip.open(seed, "wb") as f:
            f.write(b"CREATE TABLE foo (id INT);\n")
        return spec_dir, seed

    def test_skip_when_db_already_has_user_tables(self, fake_seed: tuple[Path, Path]) -> None:
        spec_dir, _ = fake_seed
        with patch("fabrik.drivers.postgres._count_user_tables", return_value=3), \
             patch("fabrik.drivers.postgres.scp_to_vps") as mock_scp, \
             patch("fabrik.drivers.postgres._run_sql") as mock_run, \
             patch("fabrik.drivers.postgres.ssh") as mock_ssh:
            result = postgres._restore_seed(
                spec_dir=spec_dir,
                seed_relpath="backups/calendar_engine_seed.sql.gz",
                container="postgres-main",
                db_user="calendar_user",
                db_name="calendar_engine",
            )
        assert result == {"status": "skipped", "reason": "db_not_empty", "user_tables": 3}
        mock_scp.assert_not_called()
        mock_run.assert_not_called()
        mock_ssh.assert_not_called()

    def test_restore_when_db_empty(self, fake_seed: tuple[Path, Path]) -> None:
        spec_dir, seed = fake_seed
        with patch("fabrik.drivers.postgres._count_user_tables", return_value=0), \
             patch("fabrik.drivers.postgres.scp_to_vps") as mock_scp, \
             patch("fabrik.drivers.postgres.ssh") as mock_ssh:
            mock_ssh.return_value = ""  # quiet docker exec
            result = postgres._restore_seed(
                spec_dir=spec_dir,
                seed_relpath="backups/calendar_engine_seed.sql.gz",
                container="postgres-main",
                db_user="calendar_user",
                db_name="calendar_engine",
            )
        assert result["status"] == "restored"
        assert mock_scp.call_count == 1
        # scp target is /tmp/fabrik-seed-*.sql.gz with a unique suffix.
        # Inspect call (works for both positional and kwarg invocations).
        scp_args = mock_scp.call_args
        local_path = scp_args.kwargs.get("local_path")
        remote_path = scp_args.kwargs.get("remote_path")
        assert local_path == str(seed)
        assert remote_path.startswith("/tmp/fabrik-seed-")
        assert remote_path.endswith(".sql.gz")
        # Verify docker exec pipeline was invoked + cleanup
        ssh_calls = [str(c) for c in mock_ssh.call_args_list]
        assert any("docker exec -i postgres-main" in s for s in ssh_calls)
        assert any("gunzip" in s and "psql" in s for s in ssh_calls)
        assert any("rm -f" in s and "/tmp/fabrik-seed-" in s for s in ssh_calls)

    def test_cleanup_runs_on_psql_failure(self, fake_seed: tuple[Path, Path]) -> None:
        """If `docker exec ... psql` fails, the temp dump on VPS must still
        be deleted (no sensitive data left behind)."""
        spec_dir, _ = fake_seed
        with patch("fabrik.drivers.postgres._count_user_tables", return_value=0), \
             patch("fabrik.drivers.postgres.scp_to_vps"), \
             patch("fabrik.drivers.postgres.ssh") as mock_ssh:
            # First ssh call (the gunzip|psql one) raises; cleanup should still run
            def side(*args, **kw):
                if "docker exec" in args[0] and "psql" in args[0]:
                    raise RuntimeError("psql died mid-restore")
                return ""
            mock_ssh.side_effect = side

            with pytest.raises(RuntimeError, match="psql died"):
                postgres._restore_seed(
                    spec_dir=spec_dir,
                    seed_relpath="backups/calendar_engine_seed.sql.gz",
                    container="postgres-main",
                    db_user="calendar_user",
                    db_name="calendar_engine",
                )

            # Cleanup must have been attempted regardless
            ssh_calls = [str(c) for c in mock_ssh.call_args_list]
            assert any("rm -f" in s and "/tmp/fabrik-seed-" in s for s in ssh_calls)


# ---------------------------------------------------------------------------
# Spec model accepts postgres_seed field
# ---------------------------------------------------------------------------
class TestSpecDependsPostgresSeed:
    def test_depends_accepts_postgres_seed(self) -> None:
        from fabrik.spec_loader import Depends
        d = Depends(postgres="calendar_engine", postgres_seed="backups/seed.sql.gz")
        assert d.postgres == "calendar_engine"
        assert d.postgres_seed == "backups/seed.sql.gz"

    def test_depends_postgres_seed_optional(self) -> None:
        from fabrik.spec_loader import Depends
        d = Depends(postgres="x")
        assert d.postgres_seed is None
