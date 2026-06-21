"""Unit tests for fabrik.drivers.postgres — mocked ssh, no VPS required."""

from __future__ import annotations

import base64
from unittest.mock import patch

import pytest

from fabrik.drivers import postgres
from fabrik.drivers.postgres import (
    PASSWORD_ALPHABET,
    PASSWORD_LENGTH,
    POSTGRES_CONTAINER,
    _generate_password,
    _validate_identifier,
    create_database,
)

# --------------------------------------------------------------------------- #
# _validate_identifier                                                         #
# --------------------------------------------------------------------------- #


class TestValidateIdentifier:
    def test_letter_leading_ok(self):
        _validate_identifier("my_project", "database")

    def test_underscore_leading_ok(self):
        _validate_identifier("_internal", "database")

    def test_digits_in_body_ok(self):
        _validate_identifier("proj_2026", "database")

    def test_digit_leading_rejected(self):
        with pytest.raises(ValueError, match="database"):
            _validate_identifier("2project", "database")

    def test_hyphen_rejected(self):
        with pytest.raises(ValueError):
            _validate_identifier("my-project", "database")

    def test_space_rejected(self):
        with pytest.raises(ValueError):
            _validate_identifier("my project", "database")

    def test_quote_rejected(self):
        """Classic SQL injection surface — must be rejected."""
        with pytest.raises(ValueError):
            _validate_identifier('x"; DROP DATABASE postgres; --', "database")

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            _validate_identifier("", "database")

    def test_too_long_rejected(self):
        with pytest.raises(ValueError):
            _validate_identifier("a" * 100, "database")

    def test_error_message_names_the_role(self):
        with pytest.raises(ValueError, match="user"):
            _validate_identifier("bad-name", "user")

    def test_non_string_rejected(self):
        with pytest.raises(ValueError):
            _validate_identifier(None, "database")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# _generate_password                                                           #
# --------------------------------------------------------------------------- #


class TestGeneratePassword:
    def test_length_is_32(self):
        assert len(_generate_password()) == PASSWORD_LENGTH == 32

    def test_alphabet_is_alphanumeric(self):
        pw = _generate_password()
        assert all(c in PASSWORD_ALPHABET for c in pw)

    def test_passwords_differ_across_calls(self):
        """CSPRNG — collision probability is negligible."""
        passwords = {_generate_password() for _ in range(50)}
        assert len(passwords) == 50


# --------------------------------------------------------------------------- #
# create_database — patched at _run_sql boundary                               #
# --------------------------------------------------------------------------- #


def _decode_call(cmd: str) -> str:
    """Extract the SQL payload from an `echo <b64> | base64 -d | ...` ssh cmd."""
    # cmd looks like: echo <b64> | base64 -d | sudo docker exec -i ... psql ...
    token = cmd.split()[1]
    return base64.b64decode(token).decode()


class TestCreateDatabase:
    def test_existing_database_returns_exists_without_creating(self):
        with patch.object(postgres, "_run_sql", return_value="1") as mock_run:
            result = create_database("my_proj")
        assert result == {"status": "exists", "database": "my_proj"}
        assert mock_run.call_count == 1
        sent_sql = mock_run.call_args.args[0]
        assert "SELECT 1 FROM pg_database" in sent_sql
        assert "datname='my_proj'" in sent_sql

    def test_new_database_no_user_runs_two_sql_batches(self):
        calls: list[str] = []

        def fake(sql, **_kw):
            calls.append(sql)
            return "" if "SELECT" in sql else ""

        with patch.object(postgres, "_run_sql", side_effect=fake):
            result = create_database("my_proj")
        assert result == {"status": "created", "database": "my_proj"}
        assert len(calls) == 2
        assert "CREATE DATABASE" in calls[1]
        assert '"my_proj"' in calls[1]

    def test_new_database_with_user_generates_password_in_single_batch(self):
        """Role + GRANT must be one SQL batch to keep idempotency atomic."""
        calls: list[str] = []

        def fake(sql, **_kw):
            calls.append(sql)
            return "" if "SELECT" in sql else ""

        with patch.object(postgres, "_run_sql", side_effect=fake):
            result = create_database("my_proj", "my_user")

        assert result["status"] == "created"
        assert result["database"] == "my_proj"
        assert result["user"] == "my_user"
        assert len(result["password"]) == PASSWORD_LENGTH
        assert all(c in PASSWORD_ALPHABET for c in result["password"])

        # 3 batches: existence SELECT, CREATE DATABASE, (CREATE ROLE + GRANT merged)
        assert len(calls) == 3
        assert "pg_database" in calls[0]
        assert "CREATE DATABASE" in calls[1]
        assert "DO $$" in calls[2]
        assert "CREATE ROLE" in calls[2]
        assert "GRANT ALL PRIVILEGES" in calls[2]
        assert 'ALTER DATABASE "my_proj" OWNER TO "my_user"' in calls[2]  # role owns DB → RLS
        assert result["password"] in calls[2]

    def test_db_user_equal_to_postgres_skips_role_creation(self):
        calls: list[str] = []

        def fake(sql, **_kw):
            calls.append(sql)
            return ""

        with patch.object(postgres, "_run_sql", side_effect=fake):
            result = create_database("my_proj", "postgres")

        assert result == {"status": "created", "database": "my_proj"}
        assert "password" not in result
        # Existence + CREATE DATABASE only
        assert len(calls) == 2

    def test_dry_run_skips_mutations(self):
        with patch.object(postgres, "_run_sql", return_value="") as mock_run:
            result = create_database("my_proj", "my_user", dry_run=True)
        assert result == {
            "status": "dry_run",
            "database": "my_proj",
            "user": "my_user",
        }
        # Existence check still called once (with dry_run=True propagated)
        assert mock_run.call_count == 1
        assert mock_run.call_args.kwargs.get("dry_run") is True

    def test_invalid_db_name_raises_before_run_sql(self):
        with patch.object(postgres, "_run_sql") as mock_run:
            with pytest.raises(ValueError, match="database"):
                create_database("bad-name")
            mock_run.assert_not_called()

    def test_invalid_db_user_raises_before_run_sql(self):
        with patch.object(postgres, "_run_sql") as mock_run:
            with pytest.raises(ValueError, match="user"):
                create_database("my_proj", "bad user")
            mock_run.assert_not_called()


# --------------------------------------------------------------------------- #
# _run_sql — wire-format tests (patched at ssh boundary)                       #
# --------------------------------------------------------------------------- #


class TestRunSqlWireFormat:
    """Confirm stdin-piping + base64 encoding reach the ssh() layer correctly."""

    def test_default_container_is_verified_uuid(self):
        with patch.object(postgres, "ssh", return_value="") as mock_ssh:
            postgres._run_sql("SELECT 1;", POSTGRES_CONTAINER)
        cmd = mock_ssh.call_args.args[0]
        assert POSTGRES_CONTAINER in cmd
        assert "psql -U postgres -tA" in cmd
        assert "docker exec -i" in cmd  # -i required for stdin piping
        assert "base64 -d" in cmd

    def test_container_override_flows_through(self):
        with patch.object(postgres, "ssh", return_value="") as mock_ssh:
            postgres._run_sql("SELECT 1;", "postgres-test-xyz")
        cmd = mock_ssh.call_args.args[0]
        assert "postgres-test-xyz" in cmd
        assert POSTGRES_CONTAINER not in cmd

    def test_sql_is_base64_encoded_on_the_wire(self):
        sql = "SELECT * FROM users WHERE name='O''Brien';"
        with patch.object(postgres, "ssh", return_value="") as mock_ssh:
            postgres._run_sql(sql, POSTGRES_CONTAINER)
        cmd = mock_ssh.call_args.args[0]
        decoded = _decode_call(cmd)
        assert decoded == sql

    def test_dollar_dollar_survives_encoding(self):
        """Regression: ``$$`` must NOT be interpreted as the shell PID."""
        sql = "DO $$ BEGIN RAISE NOTICE 'hi'; END $$;"
        with patch.object(postgres, "ssh", return_value="") as mock_ssh:
            postgres._run_sql(sql, POSTGRES_CONTAINER)
        cmd = mock_ssh.call_args.args[0]
        # The wire command must NOT contain literal $$ outside the base64 blob
        # (base64 alphabet is [A-Za-z0-9+/=] so it cannot contain $).
        assert "$$" not in cmd
        decoded = _decode_call(cmd)
        assert "DO $$" in decoded

    def test_dry_run_does_not_invoke_ssh(self):
        with patch.object(postgres, "ssh") as mock_ssh:
            result = postgres._run_sql("SELECT 1;", POSTGRES_CONTAINER, dry_run=True)
        mock_ssh.assert_not_called()
        assert result == ""

    def test_ssh_failure_propagates_runtime_error(self):
        def failing_ssh(*_args, **_kw):
            raise RuntimeError("ssh failed: connection refused")

        with patch.object(postgres, "ssh", side_effect=failing_ssh):
            with pytest.raises(RuntimeError, match="connection refused"):
                postgres._run_sql("SELECT 1;", POSTGRES_CONTAINER)
