"""Behavior Contract for T03 (audit-log-everywhere) — `src/fabrik/app_role_check.py`.

Seam test (Interfaces, T02 → T03/T04): `run_check` calls T02's `probe_app_role`,
carries its failures verbatim, and turns any exception it raises into a failure
string. `tests/test_app_role_provision.py` (T04) is the other side of that seam.

Also covers acceptance-review pass 1 fixups (T03-fixups-r1.md, items 1-7): raw-line
pattern matching vs. comment-scoped suppression, connection-source suppression,
structural compose-service location, run_check's broad fail-closed exception
handling, content-based alembic env detection, widened pattern coverage, and the
comment-marker/non-git/timeout tests item 7 names explicitly.
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
    SpecResolutionError,
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
        # Fixup item 6 — widened DDL modifiers + trigger.
        ("app/views.py", "cur.execute('CREATE OR REPLACE VIEW v AS SELECT 1')\n", "runtime DDL"),
        ("app/views2.py", "cur.execute('CREATE MATERIALIZED VIEW v AS SELECT 1')\n", "runtime DDL"),
        ("app/tmp.py", "cur.execute('CREATE TEMP TABLE t (id int)')\n", "runtime DDL"),
        ("app/tmp2.py", "cur.execute('CREATE TEMPORARY TABLE t (id int)')\n", "runtime DDL"),
        ("app/unlogged.py", "cur.execute('CREATE UNLOGGED TABLE t (id int)')\n", "runtime DDL"),
        ("app/trig.py", "cur.execute('CREATE TRIGGER trg BEFORE INSERT ON t')\n", "runtime DDL"),
        # Fixup item 6 — alembic with options, exec form, python API.
        ("scripts/a.sh", "alembic -c alembic.ini upgrade head\n", "alembic upgrade/downgrade"),
        ("scripts/b.sh", "alembic --raiseerr upgrade head\n", "alembic upgrade/downgrade"),
        (
            "app/x.py",
            "subprocess.run(['alembic', 'upgrade', 'head'])\n",
            "alembic upgrade/downgrade",
        ),
        ("app/y.py", "command.upgrade(alembic_cfg, 'head')\n", "alembic upgrade/downgrade"),
        ("app/z.py", "command.downgrade(alembic_cfg, '-1')\n", "alembic upgrade/downgrade"),
        # Fixup item 6 — new walkable file types.
        ("Procfile", "release: alembic upgrade head\n", "alembic upgrade/downgrade"),
        ("justfile", 'migrate:\n    psql "$DATABASE_URL" -f db/schema.sql\n', "psql invocation"),
        (
            "app/component.tsx",
            "await prisma.$executeRaw`op.create_table('t')`\n",
            "op.create_table",
        ),
        ("app/config.cjs", "module.exports.sync = () => db.sync()\n", ".sync("),
    ],
)
def test_scan_repo_finds_each_pattern_site(tmp_path, rel_path, content, expected_pattern):
    repo = tmp_path / "repo"
    _write(repo / rel_path, content)

    result = scan_repo(repo)

    assert result.files_scanned == 1
    findings = [f for f in result.findings if f.pattern == expected_pattern]
    assert len(findings) == 1, result.findings


@pytest.mark.parametrize("compose_name", ["compose.yml", "docker-compose.yaml"])
def test_scan_repo_walks_additional_compose_filenames(tmp_path, compose_name):
    repo = tmp_path / "repo"
    _write(repo / compose_name, "services:\n  migrate:\n    command: echo hi\n")

    result = scan_repo(repo)

    assert result.files_scanned == 1
    assert any(f.pattern == "compose service named migrate" for f in result.findings)


def test_scan_repo_full_given_repo_one_finding_per_site_and_schema_sql_excluded(tmp_path):
    """The ticket's own Given: every named site produces a finding; `db/schema.sql`
    (DDL data, not an invocation) and the same DDL text under excluded dirs do not."""
    repo = tmp_path / "repo"
    _write(repo / "app" / "db.py", "    await conn.run_sync(metadata.create_all)\n")
    _write(repo / "app" / "models.py", "    create unique index ix on t(c);\n")
    _write(
        repo / "alembic" / "env.py",
        'from alembic import context\n    url = os.environ["DATABASE_URL"]\n',
    )
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  migrate:\n"
        "    command: alembic upgrade head\n"
        "  api:\n"
        "    environment:\n"
        "      DATABASE_URL: postgresql://owner:pw@host/db\n",
    )
    _write(repo / "entrypoint.sh", 'psql "$DATABASE_URL" -f db/schema.sql\n')
    _write(repo / "db" / "schema.sql", "CREATE TABLE t (id int);\n")

    # Same DDL text under every excluded directory — must never be scanned.
    _write(repo / "tests" / "test_x.py", "create unique index ix on t(c);\n")
    _write(repo / ".venv" / "lib" / "x.py", "create unique index ix on t(c);\n")
    _write(repo / "node_modules" / "pkg" / "x.js", "create unique index ix on t(c);\n")
    _write(repo / "libs" / "shared" / "x.py", "create unique index ix on t(c);\n")

    result = scan_repo(repo)

    findings_by_path = {f.path: f.pattern for f in result.findings if f.path != "compose.yaml"}
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


# ── Fixup item 1: patterns match RAW line, never a stripped one ───────────── #


@pytest.mark.parametrize(
    ("content", "expected_pattern"),
    [
        # A `#` inside a string literal must not truncate what follows it.
        ('x = "id#1"; os.system(\'psql "$DATABASE_URL" -f db/schema.sql\')\n', "psql invocation"),
        # `postgresql://` contains `//`, which must not be read as a JS comment.
        ('run(f"postgresql://u:p@h/d"); alembic upgrade head\n', "alembic upgrade/downgrade"),
        # A `#` inside a SQL string literal must not hide the DDL that follows.
        ("SELECT '#'; CREATE TABLE t (id int);\n", "runtime DDL"),
        # Bash parameter expansion `${VAR#pattern}` uses `#` for substring removal.
        ("flag=${DATABASE_URL#*x}; drizzle-kit push\n", "drizzle-kit push"),
        # JS decrement `i--` must not be read as a SQL-style `--` comment.
        ("i--; op.create_table('t')\n", "op.create_table"),
    ],
)
def test_comment_stripping_never_hides_a_real_finding(tmp_path, content, expected_pattern):
    repo = tmp_path / "repo"
    _write(repo / "app" / "x.py", content)

    result = scan_repo(repo)

    assert any(f.pattern == expected_pattern for f in result.findings), result.findings


# ── Fixup item 2 / item 7: suppression follows the CONNECTION SOURCE ──────── #


def test_suppression_owner_as_real_connection_source_clears_every_site(tmp_path):
    repo = tmp_path / "repo"
    _write(
        repo / "app" / "db.py",
        "    engine = make_engine(os.environ['DATABASE_URL_OWNER']); "
        "conn.run_sync(metadata.create_all)\n",
    )
    _write(
        repo / "app" / "models.py",
        "    create unique index ix on t(c) using os.environ['DATABASE_URL_OWNER'];\n",
    )
    _write(
        repo / "alembic" / "env.py",
        'from alembic import context\n    url = os.environ["DATABASE_URL_OWNER"]\n',
    )
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  migrate:\n"
        '    command: sh -c "DATABASE_URL_OWNER=$DATABASE_URL_OWNER alembic upgrade head"\n'
        "  api:\n"
        "    environment:\n"
        "      DATABASE_URL: ${DATABASE_URL_OWNER}\n",
    )
    _write(repo / "entrypoint.sh", 'psql "$DATABASE_URL_OWNER" -f db/schema.sql\n')
    _write(repo / "db" / "schema.sql", "CREATE TABLE t (id int);\n")

    result = scan_repo(repo)

    assert result.findings == []


@pytest.mark.parametrize("marker", ["#", "--", "//"])
def test_suppression_never_applies_when_owner_is_only_in_a_trailing_comment(tmp_path, marker):
    repo = tmp_path / "repo"
    _write(
        repo / "entrypoint.sh",
        f'psql "$DATABASE_URL" -f db/schema.sql  {marker} was DATABASE_URL_OWNER once\n',
    )

    result = scan_repo(repo)

    assert len(result.findings) == 1
    assert result.findings[0].pattern == "psql invocation"


def test_suppression_never_applies_when_bare_database_url_also_named(tmp_path):
    """`os.getenv("DATABASE_URL_OWNER") or os.environ["DATABASE_URL"]` still reaches
    DATABASE_URL on the fallback branch — token PRESENCE alone must not suppress."""
    repo = tmp_path / "repo"
    _write(
        repo / "entrypoint.sh",
        "psql \"$(python3 -c 'import os; "
        'print(os.getenv("DATABASE_URL_OWNER") or os.environ["DATABASE_URL"])\')" '
        "-f db/schema.sql\n",
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


def test_compose_environment_passthrough_is_not_a_finding_at_all(tmp_path):
    """`DATABASE_URL: ${DATABASE_URL}` just forwards the same `.env` value — it is
    not an override, so it must not even register as a suppressed finding."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n  api:\n    environment:\n      DATABASE_URL: ${DATABASE_URL}\n",
    )

    result = scan_repo(repo)

    assert result.findings == []


def test_compose_environment_owner_value_is_suppressed(tmp_path):
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n  api:\n    environment:\n      DATABASE_URL: ${DATABASE_URL_OWNER}\n",
    )

    result = scan_repo(repo)

    assert result.findings == []


def test_compose_environment_hardcoded_override_is_a_finding_despite_owner_mentioned_elsewhere_in_block(
    tmp_path,
):
    """A service whose `command:` merely PASSES DATABASE_URL_OWNER through (as an
    unrelated flag) must not excuse its OWN environment hard-coding a different,
    non-owner-referencing DATABASE_URL value — classification is per-entry, keyed
    on that entry's value, never on whether the word appears anywhere in the block."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  api:\n"
        "    command: FALLBACK_VAR=DATABASE_URL_OWNER run-app\n"
        "    environment:\n"
        "      DATABASE_URL: postgresql://hardcoded/db\n",
    )

    result = scan_repo(repo)

    assert any(f.pattern == "compose environment sets DATABASE_URL" for f in result.findings)


# ── Fixup item 3: compose services located STRUCTURALLY ───────────────────── #


def test_compose_service_located_structurally_not_via_depends_on_or_secrets(tmp_path):
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "secrets:\n"
        "  api:\n"
        "    file: ./secret.txt\n"
        "services:\n"
        "  worker:\n"
        "    depends_on:\n"
        "      migrate:\n"
        "        condition: service_completed_successfully\n"
        "  migrate:\n"
        "    command: alembic upgrade head\n",
    )

    result = scan_repo(repo)

    migrate_findings = [f for f in result.findings if f.pattern == "compose service named migrate"]
    assert len(migrate_findings) == 1
    # The real `services.migrate:` key is on line 9 (1-indexed) — not the
    # `depends_on: migrate:` decoy on line 7, and not the `secrets: api:` block.
    assert migrate_findings[0].line == 9


def test_compose_flow_style_service_block_unlocatable_fails_closed(tmp_path):
    """A one-line flow-style compose file: the structural block can't be located,
    so suppression must be skipped entirely — the finding stays, even though the
    service's own command names DATABASE_URL_OWNER."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        'services: {migrate: {command: "DATABASE_URL_OWNER=$DATABASE_URL_OWNER alembic upgrade head"}}\n',
    )

    result = scan_repo(repo)

    assert any(f.pattern == "compose service named migrate" for f in result.findings)


def test_compose_file_unparseable_is_a_finding_never_a_silent_empty_result(tmp_path):
    repo = tmp_path / "repo"
    # A genuinely malformed document (unclosed flow sequence) — `!reset`/`!override`
    # are valid Compose tags now understood by the loader (fixup r2, item 5) and
    # must NOT read as unparseable; only a real YAML syntax error should.
    _write(repo / "compose.yaml", "services: [migrate\n")

    result = scan_repo(repo)

    assert len(result.findings) == 1
    assert result.findings[0].pattern == "compose file unparseable"


@pytest.mark.parametrize("tag", ["!reset", "!override"])
def test_compose_reset_and_override_tags_are_understood_not_unparseable(tmp_path, tag):
    """Compose's own merge directives are valid YAML for Compose's purposes — a
    loader that can't understand them must not report a real compose file as
    broken (fixup r2, item 5)."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        f"services:\n  migrate:\n    environment: {tag} [DATABASE_URL]\n",
    )

    result = scan_repo(repo)

    assert not any(f.pattern == "compose file unparseable" for f in result.findings)
    assert any(f.pattern == "compose service named migrate" for f in result.findings)


# ── Fixup item 5: alembic env.py wherever it lives, content-based ─────────── #


def test_alembic_env_recognized_by_import_wherever_it_lives(tmp_path):
    repo = tmp_path / "repo"
    _write(
        repo / "migrations" / "env.py",
        "from alembic import context\nurl = settings.database_url\n",
    )

    result = scan_repo(repo)

    assert any(
        f.path == "migrations/env.py"
        and f.pattern == "alembic env.py DATABASE_URL connection source"
        for f in result.findings
    )


def test_env_py_without_alembic_import_is_not_treated_as_alembic_env(tmp_path):
    repo = tmp_path / "repo"
    _write(repo / "config" / "env.py", "DATABASE_URL = os.environ['DATABASE_URL']\n")

    result = scan_repo(repo)

    assert result.findings == []
    assert result.files_scanned == 1


def test_alembic_env_case_insensitive_owner_suppresses(tmp_path):
    repo = tmp_path / "repo"
    _write(
        repo / "migrations" / "env.py",
        "from alembic import context\nurl = settings.database_url_owner\n",
    )

    result = scan_repo(repo)

    assert result.findings == []


# ── Fixup item 4: nothing escapes run_check ────────────────────────────────── #


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

    with patch.object(arc, "probe_app_role", return_value=[]):
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


def test_run_check_non_git_repo_dir_is_a_failure(tmp_path):
    repo = tmp_path / "repo"
    _write(repo / "app.py", "print('hi')\n")  # a real dir, never `git init`-ed

    with patch.object(arc, "probe_app_role", return_value=[]):
        result = run_check("mydb", repo)

    assert result.ok is False
    assert any("could not fetch upstream" in f for f in result.failures)


def test_stale_clone_failure_catches_fetch_timeout(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    with patch.object(
        arc.subprocess,
        "run",
        side_effect=subprocess.TimeoutExpired(cmd=["git", "fetch"], timeout=60),
    ):
        failure = arc._stale_clone_failure(repo)

    assert failure is not None
    assert "git fetch failed" in failure


@pytest.mark.parametrize(
    "exc",
    [
        AppRoleError("owner of mydb is postgres"),
        RuntimeError("driver blew up"),
        ValueError("bad db_name"),
        subprocess.TimeoutExpired(cmd=["docker", "exec"], timeout=30),
        OSError("connection refused"),
    ],
)
def test_run_check_turns_any_probe_exception_into_a_failure_and_still_scans(tmp_path, exc):
    """Fixup r2, item 10 (O23): the old version of this test asserted a tautology
    that passed even if run_check returned BEFORE scanning (a clean synced clone
    has no scan findings either way, so "only one failure" proved nothing). This
    plants a REAL finding and demands it be present — a run_check that skips the
    scan after the probe raises goes red here."""
    clone = _synced_clone(tmp_path)
    _write(clone / "entrypoint.sh", 'psql "$DATABASE_URL" -f db/schema.sql\n')

    with patch.object(arc, "probe_app_role", side_effect=exc):
        result = run_check("mydb", clone)

    assert result.ok is False
    assert any(str(exc) in f for f in result.failures)
    assert "entrypoint.sh:1 psql invocation reaches DATABASE_URL" in result.failures


def test_run_check_carries_probe_failures_verbatim_on_a_clean_current_repo(tmp_path):
    clone = _synced_clone(tmp_path)

    with patch.object(arc, "probe_app_role", return_value=["mydb_app has NOSUPERUSER violated"]):
        result = run_check("mydb", clone)

    assert result.ok is False
    assert "mydb_app has NOSUPERUSER violated" in result.failures


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


# ── project_repo_dir / _db_name_for_spec (Behavior Contract row 4) ─────────── #


def test_project_repo_dir_prefers_id_over_name():
    spec = {"id": "my-svc-id", "name": "my-svc-name"}
    assert project_repo_dir(spec) == Path("/opt/my-svc-id")


def test_project_repo_dir_falls_back_to_name_without_id():
    spec = {"name": "my-svc-name"}
    assert project_repo_dir(spec) == Path("/opt/my-svc-name")


def test_project_repo_dir_raises_spec_resolution_error_on_neither_id_nor_name():
    with pytest.raises(SpecResolutionError):
        project_repo_dir({})


def test_db_name_prefers_depends_postgres():
    spec = {"id": "my-svc", "depends": {"postgres": "shared_db"}}
    assert _db_name_for_spec(spec) == "shared_db"


def test_db_name_falls_back_to_name_with_hyphens_rewritten():
    spec = {"name": "my-svc"}
    assert _db_name_for_spec(spec) == "my_svc"


def test_db_name_raises_spec_resolution_error_on_neither_id_nor_name():
    with pytest.raises(SpecResolutionError):
        _db_name_for_spec({})


def test_db_name_raises_spec_resolution_error_on_non_mapping_depends():
    with pytest.raises(SpecResolutionError):
        _db_name_for_spec({"id": "x", "depends": ["postgres"]})


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


def test_cli_app_role_check_empty_spec_exits_1_never_opt_none(tmp_path):
    from click.testing import CliRunner

    from fabrik.cli import cli

    spec_path = tmp_path / "svc.yaml"
    spec_path.write_text("{}\n")

    result = CliRunner().invoke(cli, ["app-role-check", "--spec", str(spec_path)])

    assert result.exit_code == 1
    assert "/opt/None" not in result.output
    assert "✗" in result.output


def test_cli_app_role_check_depends_not_a_mapping_exits_1(tmp_path):
    from click.testing import CliRunner

    from fabrik.cli import cli

    spec_path = tmp_path / "svc.yaml"
    spec_path.write_text("id: my-svc\ndepends:\n  - postgres\n")

    result = CliRunner().invoke(cli, ["app-role-check", "--spec", str(spec_path)])

    assert result.exit_code == 1
    assert "✗" in result.output
    assert "mapping" in result.output


def test_scan_repo_missing_repo_dir_returns_empty_result(tmp_path):
    result = scan_repo(tmp_path / "nope")
    assert result == ScanResult(files_scanned=0, findings=[])


def test_finding_and_scan_result_are_plain_dataclasses():
    f = Finding(path="a.py", line=1, pattern="x")
    assert f.path == "a.py"
    assert f.line == 1
    assert f.pattern == "x"


# ── Fixups r2 (acceptance review pass 2 — residue of the r1 hunks) ─────────── #


def test_disqualifier_reads_the_raw_line_not_the_comment_stripped_one(tmp_path):
    """O17: a `#` before a SECOND, real DATABASE_URL use must not strip it away
    and make the line read as owner-only. Both invocations are `psql`, on one
    line, joined by `;` — the fake `#` inside the quoted string sits BETWEEN
    them."""
    repo = tmp_path / "repo"
    _write(
        repo / "entrypoint.sh",
        'psql "$DATABASE_URL_OWNER" -c "select 1"; x="a#b"; psql "$DATABASE_URL" -f schema.sql\n',
    )

    result = scan_repo(repo)

    assert any(f.pattern == "psql invocation" for f in result.findings)


def test_migrate_service_canonical_owner_handoff_is_suppressed(tmp_path):
    """O18: `DATABASE_URL: ${DATABASE_URL_OWNER}` is the canonical, intended
    hand-off — the `DATABASE_URL:` KEY text itself (a bare, word-bounded
    "DATABASE_URL") must never be counted as the bare-token disqualifier, or
    this exact canonical form would defeat its own suppression."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n  migrate:\n    environment:\n      DATABASE_URL: ${DATABASE_URL_OWNER}\n",
    )

    result = scan_repo(repo)

    assert result.findings == []


def test_owner_classification_requires_a_fullmatch_not_a_substring(tmp_path):
    """O24: a value that merely CONTAINS the owner variable's name (e.g. as a
    query-string parameter) is not the same as the value BEING that variable —
    stays an override."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  api:\n"
        "    environment:\n"
        "      DATABASE_URL: postgresql://host/db?fallback=DATABASE_URL_OWNER\n",
    )

    result = scan_repo(repo)

    assert any(f.pattern == "compose environment sets DATABASE_URL" for f in result.findings)


@pytest.mark.parametrize(
    "environment_yaml",
    [
        "      - DATABASE_URL\n",  # value-less list form
        "      DATABASE_URL:\n",  # null dict value
        "      DATABASE_URL: ${DATABASE_URL:?msg}\n",  # error-if-unset, colon form
        "      DATABASE_URL: ${DATABASE_URL?msg}\n",  # error-if-unset, no colon
    ],
)
def test_compose_environment_passthrough_forms_are_not_findings(tmp_path, environment_yaml):
    """O19: each of these means "use the same `.env` value" (optionally guarded
    against being unset) — none is an override."""
    repo = tmp_path / "repo"
    _write(repo / "compose.yaml", "services:\n  api:\n    environment:\n" + environment_yaml)

    result = scan_repo(repo)

    assert result.findings == []


def test_compose_environment_default_fallback_form_stays_an_override(tmp_path):
    """O19: `${DATABASE_URL:-default}` can silently substitute a DIFFERENT value
    when unset — that is exactly the risk this check exists to catch, so it must
    stay an override, unlike the `:?msg`/`?msg` guard forms."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n  api:\n    environment:\n      DATABASE_URL: ${DATABASE_URL:-postgresql://fallback/db}\n",
    )

    result = scan_repo(repo)

    assert any(f.pattern == "compose environment sets DATABASE_URL" for f in result.findings)


def test_services_block_end_scan_skips_a_column_zero_comment(tmp_path):
    """O26: a comment starting at column 0 is still just a comment — it must not
    read as ending the `services:` mapping (outer scan) or a service's own body
    (inner scan). Both scans carry a column-0 comment in this fixture; a
    hardcoded override past BOTH is located at its real line only when neither
    scan was fooled."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n"
        "# comment right after services: — must not end the outer block\n"
        "  migrate:\n"
        "    command: something\n"
        "# comment inside migrate's own body — must not end the inner block\n"
        "    environment:\n"
        "      DATABASE_URL: postgresql://hardcoded/db\n",
    )

    result = scan_repo(repo)

    env_findings = [
        f for f in result.findings if f.pattern == "compose environment sets DATABASE_URL"
    ]
    assert len(env_findings) == 1
    assert env_findings[0].line == 7


@pytest.mark.parametrize("bad_spec_yaml", ["- postgres\n- other\n", "42\n", "just a string\n"])
def test_db_name_and_repo_dir_raise_on_a_non_mapping_spec(bad_spec_yaml):
    """O21: a spec whose top level is a list or scalar must not reach `.get()`
    and raise a bare AttributeError."""
    import yaml as _yaml

    spec = _yaml.safe_load(bad_spec_yaml)
    with pytest.raises(SpecResolutionError, match="mapping"):
        _db_name_for_spec(spec)
    with pytest.raises(SpecResolutionError, match="mapping"):
        project_repo_dir(spec)


def test_cli_app_role_check_non_mapping_spec_exits_1(tmp_path):
    from click.testing import CliRunner

    from fabrik.cli import cli

    spec_path = tmp_path / "svc.yaml"
    spec_path.write_text("- postgres\n- other\n")

    result = CliRunner().invoke(cli, ["app-role-check", "--spec", str(spec_path)])

    assert result.exit_code == 1
    assert "✗" in result.output
    assert "mapping" in result.output


def test_alembic_submodule_import_is_recognized(tmp_path):
    """O22: `from alembic.op import ...` / `from alembic.context import ...` are
    as real an alembic env as a bare `from alembic import context`."""
    repo = tmp_path / "repo"
    _write(
        repo / "migrations" / "env.py",
        "from alembic.context import get_context\nurl = settings.database_url\n",
    )

    result = scan_repo(repo)

    assert any(
        f.pattern == "alembic env.py DATABASE_URL connection source" for f in result.findings
    )


def test_run_check_probe_exception_with_empty_str_is_never_a_blank_failure(tmp_path):
    """O25: `raise RuntimeError()` (no message) has an empty `str()` — the
    failure line must still name the exception TYPE, never read as blank."""
    clone = _synced_clone(tmp_path)

    with patch.object(arc, "probe_app_role", side_effect=RuntimeError()):
        result = run_check("mydb", clone)

    assert result.ok is False
    assert all(f.strip() for f in result.failures)
    assert any("RuntimeError" in f for f in result.failures)


# ── Fixups r3 (acceptance review pass 3 — last round; scope-growth stop fired) ── #


def test_null_database_url_key_still_counts_as_a_bare_token_use(tmp_path):
    """O27 (fail-open): `DATABASE_URL:` (null/value-less) means "inherit the host
    value" — it IS a bare DATABASE_URL use and must not be erased from the
    disqualifier text, or a sibling DATABASE_URL_OWNER line would falsely
    suppress a migrate block that still reaches the bare variable."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  migrate:\n"
        "    environment:\n"
        "      DATABASE_URL:\n"
        "      DATABASE_URL_OWNER: ${DATABASE_URL_OWNER}\n",
    )

    result = scan_repo(repo)

    assert any(f.pattern == "compose service named migrate" for f in result.findings)


def test_compose_variable_names_are_case_sensitive_for_passthrough(tmp_path):
    """O29 (fail-open): `${database_url}` is a DIFFERENT variable from
    `${DATABASE_URL}` (shell/Compose variable names are case-sensitive) — it must
    stay an override, not read as a safe pass-through."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n  api:\n    environment:\n      DATABASE_URL: ${database_url}\n",
    )

    result = scan_repo(repo)

    assert any(f.pattern == "compose environment sets DATABASE_URL" for f in result.findings)


def test_compose_variable_names_are_case_sensitive_for_owner(tmp_path):
    """O29 (fail-open): `${database_url_owner}` is not the same variable as
    `${DATABASE_URL_OWNER}` — it must stay an override, not a suppressed hand-off."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n  api:\n    environment:\n      DATABASE_URL: ${database_url_owner}\n",
    )

    result = scan_repo(repo)

    assert any(f.pattern == "compose environment sets DATABASE_URL" for f in result.findings)


def test_migrate_list_form_owner_handoff_is_suppressed(tmp_path):
    """O28 (fail-closed): `- DATABASE_URL=${DATABASE_URL_OWNER}` is the canonical
    hand-off in COMPOSE'S LIST environment form — the `DATABASE_URL=` key text
    must not itself count as a bare-token use, same as the dict-form key."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n  migrate:\n    environment:\n      - DATABASE_URL=${DATABASE_URL_OWNER}\n",
    )

    result = scan_repo(repo)

    assert result.findings == []


def test_migrate_list_form_value_less_database_url_still_counts_as_bare(tmp_path):
    """O28: a value-less list entry (`- DATABASE_URL`, no `=`) means "inherit the
    host value" — a genuine bare use — so a sibling owner hand-off elsewhere in
    the SAME block must NOT suppress the migrate finding."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  migrate:\n"
        "    environment:\n"
        "      - DATABASE_URL\n"
        "      - DATABASE_URL_OWNER=${DATABASE_URL_OWNER}\n",
    )

    result = scan_repo(repo)

    assert any(f.pattern == "compose service named migrate" for f in result.findings)
