"""Behavior Contract for T03 (audit-log-everywhere) — `src/fabrik/app_role_check.py`.

Seam test (Interfaces, T02 → T03/T04): `run_check` calls T02's `probe_app_role`,
carries its failures verbatim, and turns `AppRoleError` into a failure string.
`tests/test_app_role_provision.py` (T04) is the other side of that seam.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from fabrik import app_role_check as arc
from fabrik.app_role_check import (
    CheckResult,
    Finding,
    ScanResult,
    _db_name_for_spec,
    project_repo_dir,
    run_check,
    scan_repo,
)
from fabrik.drivers.postgres import AppRoleError


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


# ── scan_repo: one finding per pattern site (Behavior Contract row 1) ─────── #


@pytest.mark.parametrize(
    ("rel_path", "content", "expected_pattern"),
    [
        ("app/db.py", "    await conn.run_sync(metadata.create_all)\n", "create_all"),
        ("app/models.py", "    create unique index ix on t(c);\n", "runtime DDL"),
        ("scripts/migrate.py", "    op.create_table('t')\n", "op.create_table"),
        ("app/sync.js", "    sequelize.sync();\n", ".sync("),
        ("scripts/run.sh", "alembic upgrade head\n", "alembic upgrade/downgrade"),
        ("scripts/run.sh", "prisma migrate deploy\n", "prisma migrate/db push"),
        ("scripts/run.sh", "drizzle-kit push\n", "drizzle-kit push"),
        ("scripts/run.sh", "python manage.py migrate\n", "manage.py migrate"),
        ("entrypoint.sh", 'psql "$DATABASE_URL" -f db/schema.sql\n', "psql invocation"),
    ],
)
def test_scan_repo_finds_each_pattern_site(tmp_path, rel_path, content, expected_pattern):
    repo = tmp_path / "repo"
    _write(repo / rel_path, content)

    result = scan_repo(repo)

    assert result.files_scanned == 1
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.path == rel_path
    assert finding.pattern == expected_pattern
    assert finding.line == 1


def test_scan_repo_full_given_repo_one_finding_per_site_and_schema_sql_excluded(tmp_path):
    """The ticket's own Given: every named site produces a finding; `db/schema.sql`
    (DDL data, not an invocation) and the same DDL text under excluded dirs do not."""
    repo = tmp_path / "repo"
    _write(repo / "app" / "db.py", "    await conn.run_sync(metadata.create_all)\n")
    _write(repo / "app" / "models.py", "    create unique index ix on t(c);\n")
    _write(repo / "alembic" / "env.py", '    url = os.environ["DATABASE_URL"]\n')
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  migrate:\n"
        "    command: alembic upgrade head\n"
        "  api:\n"
        "    environment:\n"
        "      DATABASE_URL: ${DATABASE_URL}\n",
    )
    _write(repo / "entrypoint.sh", 'psql "$DATABASE_URL" -f db/schema.sql\n')
    _write(repo / "db" / "schema.sql", "CREATE TABLE t (id int);\n")

    # Same DDL text under every excluded directory — must never be scanned.
    _write(repo / "tests" / "test_x.py", "create unique index ix on t(c);\n")
    _write(repo / ".venv" / "lib" / "x.py", "create unique index ix on t(c);\n")
    _write(repo / "node_modules" / "pkg" / "x.js", "create unique index ix on t(c);\n")
    _write(repo / "libs" / "shared" / "x.py", "create unique index ix on t(c);\n")

    result = scan_repo(repo)

    findings_by_path = {f.path: f.pattern for f in result.findings}
    assert findings_by_path["app/db.py"] == "create_all"
    assert findings_by_path["app/models.py"] == "runtime DDL"
    assert findings_by_path["alembic/env.py"] == "alembic env.py DATABASE_URL connection source"
    assert findings_by_path["entrypoint.sh"] == "psql invocation"
    # compose.yaml carries three independent sites in one file.
    compose_patterns = {f.pattern for f in result.findings if f.path == "compose.yaml"}
    assert compose_patterns == {
        "compose service named migrate",
        "alembic upgrade/downgrade",
        "compose environment sets DATABASE_URL",
    }
    # Nothing from db/schema.sql or any excluded directory.
    scanned_paths = {f.path for f in result.findings}
    assert "db/schema.sql" not in scanned_paths
    assert not any(
        p.startswith(("tests/", ".venv/", "node_modules/", "libs/")) for p in scanned_paths
    )
    # files_scanned counts only walkable files: db.py, models.py, env.py, compose.yaml,
    # entrypoint.sh — never schema.sql or anything under a skipped directory.
    assert result.files_scanned == 5


# ── Suppression (Behavior Contract row 2) ─────────────────────────────────── #


def test_suppression_owner_as_real_connection_source_clears_every_site(tmp_path):
    repo = tmp_path / "repo"
    _write(
        repo / "app" / "db.py",
        "    await conn.run_sync(metadata.create_all)  "
        'if os.environ["DATABASE_URL_OWNER"] else None\n',
    )
    _write(
        repo / "app" / "models.py",
        "    create unique index ix on t(c) using os.environ['DATABASE_URL_OWNER'];\n",
    )
    _write(repo / "alembic" / "env.py", '    url = os.environ["DATABASE_URL_OWNER"]\n')
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  migrate:\n"
        '    command: sh -c "DATABASE_URL_OWNER=$DATABASE_URL_OWNER alembic upgrade head"\n'
        "  api:\n"
        "    environment:\n"
        "      DATABASE_URL_OWNER: ${DATABASE_URL_OWNER}\n",
    )
    _write(repo / "entrypoint.sh", 'psql "$DATABASE_URL_OWNER" -f db/schema.sql\n')
    _write(repo / "db" / "schema.sql", "CREATE TABLE t (id int);\n")

    result = scan_repo(repo)

    assert result.findings == []


def test_suppression_never_applies_when_owner_is_only_in_a_trailing_comment(tmp_path):
    repo = tmp_path / "repo"
    _write(
        repo / "entrypoint.sh",
        'psql "$DATABASE_URL" -f db/schema.sql  # was DATABASE_URL_OWNER once\n',
    )

    result = scan_repo(repo)

    assert len(result.findings) == 1
    assert result.findings[0].pattern == "psql invocation"


def test_suppression_compose_block_spans_environment_and_command_not_just_one_line(tmp_path):
    """A `migrate` service's own name-line never mentions DATABASE_URL_OWNER — the
    suppression must look at the whole service block (its command), per spec wording."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  migrate:\n"
        '    command: sh -c "DATABASE_URL_OWNER=$DATABASE_URL_OWNER alembic upgrade head"\n',
    )

    result = scan_repo(repo)

    assert result.findings == []


# ── run_check: fail-closed cobra counters (Behavior Contract row 3) ───────── #


def test_run_check_missing_repo_dir_is_a_failure(tmp_path):
    missing = tmp_path / "does-not-exist"
    with patch.object(arc, "probe_app_role", return_value=[]):
        result = run_check("mydb", missing)

    assert result.ok is False
    assert any(f"no repo at {missing}" in f for f in result.failures)


def test_run_check_zero_walkable_files_is_a_failure(tmp_path):
    repo = tmp_path / "repo"
    _write(repo / "db" / "schema.sql", "CREATE TABLE t (id int);\n")  # not walkable

    with (
        patch.object(arc, "probe_app_role", return_value=[]),
        patch.object(arc, "_stale_clone_failure", return_value=None),
    ):
        result = run_check("mydb", repo)

    assert result.ok is False
    assert any(f"scanned 0 files under {repo}" in f for f in result.failures)


def test_run_check_stale_clone_is_a_failure(tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git(["init", "-q"], upstream)
    _git(["config", "user.email", "t@fabrik.local"], upstream)
    _git(["config", "user.name", "t"], upstream)
    _write(upstream / "README.md", "one\n")
    _git(["add", "README.md"], upstream)
    _git(["commit", "-q", "-m", "one"], upstream)

    clone = tmp_path / "clone"
    _git(["clone", "-q", str(upstream), str(clone)], tmp_path)

    # Diverge upstream after the clone was made.
    _write(upstream / "README.md", "two\n")
    _git(["add", "README.md"], upstream)
    _git(["commit", "-q", "-m", "two"], upstream)

    with (
        patch.object(arc, "probe_app_role", return_value=[]),
    ):
        result = run_check("mydb", clone)

    assert result.ok is False
    assert any(f.startswith("stale clone: HEAD ") for f in result.failures)


def test_run_check_no_upstream_is_a_failure(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-q"], repo)
    _git(["config", "user.email", "t@fabrik.local"], repo)
    _git(["config", "user.name", "t"], repo)
    _write(repo / "README.md", "one\n")
    _git(["add", "README.md"], repo)
    _git(["commit", "-q", "-m", "one"], repo)

    with patch.object(arc, "probe_app_role", return_value=[]):
        result = run_check("mydb", repo)

    assert result.ok is False
    assert any(f"no upstream configured for {repo}" in f for f in result.failures)


def _synced_clone(tmp_path: Path) -> Path:
    """A clone that is up to date with its upstream — the "clean current repo" case."""
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git(["init", "-q"], upstream)
    _git(["config", "user.email", "t@fabrik.local"], upstream)
    _git(["config", "user.name", "t"], upstream)
    _write(upstream / "app.py", "print('hi')\n")
    _git(["add", "app.py"], upstream)
    _git(["commit", "-q", "-m", "one"], upstream)

    clone = tmp_path / "clone"
    _git(["clone", "-q", str(upstream), str(clone)], tmp_path)
    return clone


def test_run_check_carries_probe_failures_verbatim_on_a_clean_current_repo(tmp_path):
    clone = _synced_clone(tmp_path)

    with patch.object(arc, "probe_app_role", return_value=["mydb_app has NOSUPERUSER violated"]):
        result = run_check("mydb", clone)

    assert result.ok is False
    assert "mydb_app has NOSUPERUSER violated" in result.failures


def test_run_check_turns_app_role_error_into_a_failure_string(tmp_path):
    clone = _synced_clone(tmp_path)

    with patch.object(arc, "probe_app_role", side_effect=AppRoleError("owner of mydb is postgres")):
        result = run_check("mydb", clone)

    assert result.ok is False
    assert any("owner of mydb is postgres" in f for f in result.failures)


def test_run_check_passes_when_probe_clean_and_repo_current_with_no_findings(tmp_path):
    clone = _synced_clone(tmp_path)

    with patch.object(arc, "probe_app_role", return_value=[]):
        result = run_check("mydb", clone)

    assert result.ok is True
    assert result.failures == []


def test_run_check_failure_format_is_path_line_pattern_reaches_database_url(tmp_path):
    clone = _synced_clone(tmp_path)
    _write(clone / "entrypoint.sh", 'psql "$DATABASE_URL" -f db/schema.sql\n')

    with patch.object(arc, "probe_app_role", return_value=[]):
        result = run_check("mydb", clone)

    assert "entrypoint.sh:1 psql invocation reaches DATABASE_URL" in result.failures


# ── project_repo_dir (Behavior Contract row 4) ─────────────────────────────── #


def test_project_repo_dir_prefers_id_over_name():
    spec = {"id": "my-svc-id", "name": "my-svc-name"}
    assert project_repo_dir(spec) == Path("/opt/my-svc-id")


def test_project_repo_dir_falls_back_to_name_without_id():
    spec = {"name": "my-svc-name"}
    assert project_repo_dir(spec) == Path("/opt/my-svc-name")


# ── db_name derivation (used by the CLI, mirrors infrastructure.py) ───────── #


def test_db_name_prefers_depends_postgres():
    spec = {"id": "my-svc", "depends": {"postgres": "shared_db"}}
    assert _db_name_for_spec(spec) == "shared_db"


def test_db_name_falls_back_to_name_with_hyphens_rewritten():
    spec = {"name": "my-svc"}
    assert _db_name_for_spec(spec) == "my_svc"


# ── CLI (Behavior Contract row 5) ──────────────────────────────────────────── #


def _spec_path(tmp_path: Path) -> Path:
    p = tmp_path / "svc.yaml"
    p.write_text("id: my-svc\nkind: service\n")
    return p


def test_cli_app_role_check_prints_x_lines_and_exits_1_on_failure(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from fabrik.cli import cli

    spec_path = _spec_path(tmp_path)
    monkeypatch.setattr(
        "fabrik.app_role_check.run_check",
        lambda db_name, repo_dir, container=None: CheckResult(
            ok=False, failures=["boom one", "boom two"]
        ),
    )

    result = CliRunner().invoke(cli, ["app-role-check", "--spec", str(spec_path)])

    assert result.exit_code == 1
    assert "✗ boom one" in result.output
    assert "✗ boom two" in result.output


def test_cli_app_role_check_prints_check_and_exits_0_on_success(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from fabrik.cli import cli

    spec_path = _spec_path(tmp_path)
    monkeypatch.setattr(
        "fabrik.app_role_check.run_check",
        lambda db_name, repo_dir, container=None: CheckResult(ok=True, failures=[]),
    )

    result = CliRunner().invoke(cli, ["app-role-check", "--spec", str(spec_path)])

    assert result.exit_code == 0
    assert "✓" in result.output


def test_cli_app_role_check_resolves_db_name_and_repo_dir_from_spec(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from fabrik.cli import cli

    spec_path = tmp_path / "svc.yaml"
    spec_path.write_text("id: my-svc-id\nname: my-svc-name\n")

    captured: dict = {}

    def fake_run_check(db_name, repo_dir, container=None):
        captured["db_name"] = db_name
        captured["repo_dir"] = repo_dir
        return CheckResult(ok=True, failures=[])

    monkeypatch.setattr("fabrik.app_role_check.run_check", fake_run_check)

    result = CliRunner().invoke(cli, ["app-role-check", "--spec", str(spec_path)])

    assert result.exit_code == 0
    assert captured["db_name"] == "my_svc_name"
    assert captured["repo_dir"] == Path("/opt/my-svc-id")


def test_scan_repo_missing_repo_dir_returns_empty_result(tmp_path):
    result = scan_repo(tmp_path / "nope")
    assert result == ScanResult(files_scanned=0, findings=[])


def test_finding_and_scan_result_are_plain_dataclasses():
    f = Finding(path="a.py", line=1, pattern="x")
    assert f.path == "a.py"
    assert f.line == 1
    assert f.pattern == "x"
