"""Highest-risk path for the subagent-runs per-project INSERT-only role
(fabrik-lib "product-aware subagents" contract): the PRIVILEGE BOUNDARY of
the SQL the registrar runs as the postgres superuser.

``create_subagent_ins_role`` mints ONE per-project role on the shared
`fabrik_analytics` DB:
  {project}_subagent_ins : INSERT-only  ->  SUBAGENT_RUNS_DSN (module writes)

If the ins role ever gained a SELECT/UPDATE/DELETE/TRUNCATE verb, a compromised
project key could exfiltrate other projects' history, alter data, or delete
audit rows — so these tests pin the exact grants AND guard against a regression
that ADDS a read/write-elsewhere grant on a separate line. They also pin the
hardening from `create_watchdog_roles`: ``ON_ERROR_STOP`` (no false-success),
password rotation ONLY on fresh create (a re-apply preserves the running
project's DSN), and the 63-char identifier guard.

All VPS mutations are mocked at the ``_run_sql`` boundary; hermetic. These
prove the EMITTED SQL only — a live-Postgres execution test is in
`test_rank_task_subagents.py` (skipif when postgres isn't reachable) for the
INSERT + SELECT-forbidden behavioral proof.
"""

from __future__ import annotations

import re
from unittest import mock

import pytest

from fabrik.drivers import postgres as pg

PROJECT = "brand_identity_creator"
ROLE = f"{PROJECT}_subagent_ins"
# Verbs the INSERT-only role must NEVER receive, on ANY line targeting this role.
_FORBIDDEN_VERBS = ("SELECT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")


def _capture(project: str = PROJECT, *, role_exists: bool = False):
    """Run create_subagent_ins_role with _run_sql/_role_exists/_generate_password
    mocked; return (result, batch_sql)."""
    calls: list[str] = []

    def fake_run_sql(sql, container=pg.POSTGRES_CONTAINER, dry_run=False):
        calls.append(sql)
        return ""

    with (
        mock.patch.object(pg, "_run_sql", side_effect=fake_run_sql),
        mock.patch.object(pg, "_role_exists", return_value=role_exists),
        mock.patch.object(pg, "_generate_password", return_value="INS_PW"),
    ):
        result = pg.create_subagent_ins_role(project)
    batch_calls = [c for c in calls if "GRANT CONNECT" in c]
    assert len(batch_calls) == 1, f"expected exactly one grant batch, got {len(batch_calls)}"
    return result, batch_calls[0]


# ── privilege boundary ────────────────────────────────────────────────────


def test_ins_role_gets_only_insert_never_a_read_or_delete_verb():
    """INSERT is the ONLY DML the role can perform on subagent_runs. A regression
    that adds e.g. `GRANT SELECT ... TO "<role>"` on a NEW line must be caught,
    including comma-separated multi-verb GRANTs like `GRANT SELECT, INSERT ...`."""
    _, sql = _capture()
    assert f'GRANT INSERT ON public.subagent_runs TO "{ROLE}";' in sql
    # Check every line naming this role — none may carry any forbidden verb.
    # Uses word-boundary regex (Finder A#5): the previous `f' {verb} ' not in line`
    # missed `GRANT SELECT, INSERT ON ...` because `SELECT,` has no trailing space
    # and doesn't start the line. `\b` matches SELECT preceded by ANY non-word char
    # (space, comma, tab, semicolon), then followed by ANY non-word char (space or
    # comma or semicolon before ON).
    for line in sql.splitlines():
        if f'"{ROLE}"' not in line:
            continue
        for verb in _FORBIDDEN_VERBS:
            assert not re.search(rf"\b{verb}\b", line), (
                f"forbidden verb {verb!r} granted to {ROLE!r} on line: {line}"
            )


def test_ins_role_gets_sequence_usage_for_bigserial_id():
    """`id BIGSERIAL` at DDL time creates `subagent_runs_id_seq`. Without USAGE
    on that sequence, INSERT would fail with `permission denied for sequence`.
    This test pins that grant so it can't drift away."""
    _, sql = _capture()
    assert f'GRANT USAGE ON SEQUENCE public.subagent_runs_id_seq TO "{ROLE}";' in sql


def test_ins_role_gets_connect_on_fabrik_analytics_only():
    """The role must be able to CONNECT to fabrik_analytics — and only there.
    A grant on a DIFFERENT database (e.g. the app DB) would mean this role could
    connect to project data even though we designed it never to."""
    _, sql = _capture()
    # CONNECT is only granted on fabrik_analytics.
    connect_lines = [line for line in sql.splitlines() if "GRANT CONNECT" in line]
    assert len(connect_lines) == 1
    assert pg.FABRIK_ANALYTICS_DB in connect_lines[0]


def test_ins_role_uses_least_privilege_options_on_create():
    """LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE — a compromised key must not be
    able to escalate to superuser, create databases, or mint new roles."""
    _, sql = _capture()
    create = next(line for line in sql.splitlines() if line.strip().startswith("CREATE ROLE"))
    assert "LOGIN" in create
    assert "NOSUPERUSER" in create
    assert "NOCREATEDB" in create
    assert "NOCREATEROLE" in create
    # A bare `SUPERUSER` — even alongside `NOSUPERUSER` — would let a rogue
    # regression `CREATE ROLE "role" WITH LOGIN NOSUPERUSER SUPERUSER ...`
    # ship: Postgres picks the LAST flag and grants superuser. The previous
    # assertion `'SUPERUSER' not in create or 'NOSUPERUSER' in create` was
    # always True whenever NOSUPERUSER was present (Finder A#7). Strip the
    # NO-prefixed form first, then reject any remaining SUPERUSER.
    create_without_no = create.replace("NOSUPERUSER", "")
    assert not re.search(r"\bSUPERUSER\b", create_without_no), (
        f"bare SUPERUSER present in CREATE ROLE: {create}"
    )


# ── failure-mode robustness ───────────────────────────────────────────────


def test_create_role_is_plain_not_wrapped_in_do_block():
    """Finder A#10: no test previously guarded against a well-intentioned regression
    that wraps CREATE ROLE in `DO $$ IF NOT EXISTS (SELECT FROM pg_roles ...) THEN
    CREATE ROLE ... END IF; END $$;` to 'fix' a perceived create race. That wrapping
    is exactly what the docstring at postgres.py forbids — under a real create race,
    the DO block silently skips CREATE, but the Python code has already generated
    `pw` and injected a DSN using it. The role in the DB has a DIFFERENT password
    → auth fails at runtime. Pin the plain CREATE ROLE discipline.
    """
    _, sql = _capture()
    assert "DO $$" not in sql, "CREATE ROLE must be plain, not wrapped in DO block"
    assert "IF NOT EXISTS" not in sql, "CREATE ROLE must not use IF NOT EXISTS"


def test_ins_role_grants_use_public_schema_qualification():
    """Finder A#9: unqualified `subagent_runs` / `subagent_runs_id_seq` grants are
    fragile — a future migration that moves the table to a different schema would
    silently target the wrong object or fail. Fully-qualified names make the
    coupling explicit and survive a search_path drift."""
    _, sql = _capture()
    assert 'GRANT INSERT ON public.subagent_runs TO' in sql, (
        f"INSERT grant must qualify table with public.: {sql}"
    )
    assert 'GRANT USAGE ON SEQUENCE public.subagent_runs_id_seq TO' in sql, (
        f"sequence USAGE grant must qualify with public.: {sql}"
    )


def test_batch_runs_under_on_error_stop_so_a_failed_grant_aborts_the_batch():
    """Without ON_ERROR_STOP, a mid-batch failure would leave the role created
    but ungranted, and this function would report success. Pin the psql \\set."""
    _, sql = _capture()
    assert "\\set ON_ERROR_STOP on" in sql
    # And it must be the FIRST line — otherwise a failure before the \\set still
    # exits 0 and reports success.
    assert sql.strip().splitlines()[0] == "\\set ON_ERROR_STOP on"


def test_password_generated_only_on_fresh_create_not_on_reapply():
    """A running project's SUBAGENT_RUNS_DSN must not be rotated on re-apply —
    the module would keep trying to connect with the OLD password from its
    baked-in `.env` and silently fall back to JSONL-only. Password is None
    when the role already exists."""
    result, _ = _capture(role_exists=True)
    assert result["ins"]["password"] is None
    assert result["ins"]["status"] == "exists"

    fresh_result, _ = _capture(role_exists=False)
    assert fresh_result["ins"]["password"] == "INS_PW"
    assert fresh_result["ins"]["status"] == "created"


def test_no_create_role_statement_when_role_already_exists():
    """A re-apply must NOT re-issue CREATE ROLE (it would error `role already
    exists` under ON_ERROR_STOP and abort the whole batch — losing the
    idempotent re-grant of privileges that IS supposed to run every time)."""
    _, sql = _capture(role_exists=True)
    assert "CREATE ROLE" not in sql, "re-apply must skip CREATE ROLE for existing role"
    # But grants must still be re-applied — verify at least the INSERT one.
    assert f'GRANT INSERT ON public.subagent_runs TO "{ROLE}";' in sql


# ── identifier guards ─────────────────────────────────────────────────────


def test_role_name_refuses_when_over_63_char_postgres_limit():
    """Postgres silently truncates identifiers past NAMEDATALEN (63). Two long
    project names could collide on the same truncated role — refuse loudly."""
    # Suffix is `_subagent_ins` (13 chars) → project must be <= 50 chars for the
    # role to fit. This project id is 51 chars → role is 64 chars → refuse.
    too_long = "a" * 51
    with pytest.raises(ValueError, match="63-char"):
        pg._subagent_ins_role_name(too_long)


def test_project_identifier_gets_regex_validated():
    """Invalid project ids (spaces, quotes, semicolons) must be rejected BEFORE
    they reach the SQL — otherwise the CREATE ROLE / GRANT string would be
    corrupted. Delegated to `_validate_identifier`."""
    with pytest.raises(ValueError):
        pg._subagent_ins_role_name("not valid; DROP TABLE users; --")


# ── dry-run marker ────────────────────────────────────────────────────────


def test_dry_run_returns_marker_without_running_sql():
    """Dry-run must never mutate the cluster — return a marker with password=None."""
    with (
        mock.patch.object(pg, "_run_sql") as run_sql_mock,
        mock.patch.object(pg, "_role_exists") as role_exists_mock,
        mock.patch.object(pg, "_generate_password") as pw_mock,
    ):
        result = pg.create_subagent_ins_role(PROJECT, dry_run=True)
    assert run_sql_mock.call_count == 0, "dry-run must not call _run_sql"
    assert role_exists_mock.call_count == 0, "dry-run must not probe role existence"
    assert pw_mock.call_count == 0, "dry-run must not generate a password"
    assert result == {"ins": {"user": ROLE, "password": None, "status": "dry_run"}}
