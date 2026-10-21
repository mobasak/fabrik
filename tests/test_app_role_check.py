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
        "    env_file:\n"
        "      - .env\n"
        "      - path: .env.owner\n"
        "        required: false\n"
        "    command: alembic upgrade head\n"
        "  api:\n"
        "    environment:\n"
        "      DATABASE_URL: ${DATABASE_URL_OWNER}\n",
    )
    _write(repo / "entrypoint.sh", 'psql "$DATABASE_URL_OWNER" -f db/schema.sql\n')
    _write(repo / "db" / "schema.sql", "CREATE TABLE t (id int);\n")

    result = scan_repo(repo)

    # Owner split (D-754): every owner-sourced SITE still clears, the `migrate` service declaring
    # `.env.owner` is the accepted owner consumer (its `alembic upgrade head` names no bare DATABASE_URL,
    # so it clears) — except the compose `environment: DATABASE_URL: ${DATABASE_URL_OWNER}` hand-off on
    # `api`, which compose interpolates from the project `.env`, where the owner key no longer lives; it
    # is the ONE finding, with its remedy.
    assert [(f.path, f.pattern) for f in result.findings] == [
        ("compose.yaml", arc.OWNER_HANDOFF_REMEDY)
    ], result.findings


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


def test_compose_command_interpolating_the_owner_key_is_the_handoff_finding(tmp_path):
    """G16 (owner split review, round 1 — check-O5): `$DATABASE_URL_OWNER` in a `command:` is compose
    interpolation from the project `.env`, which no longer holds the key — the same empty-value
    hand-off as the `environment:` form, the same remedy, at the command line. The `migrate`
    structural finding stays suppressed by the block's owner naming (that rule is unchanged); the
    hand-off finding is what blocks. Before the split this shape was clean (findings == [])."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  migrate:\n"
        '    command: sh -c "DATABASE_URL_OWNER=$DATABASE_URL_OWNER alembic upgrade head"\n',
    )

    result = scan_repo(repo)

    assert [(f.line, f.pattern) for f in result.findings] == [(3, arc.OWNER_HANDOFF_REMEDY)], (
        result.findings
    )


def test_compose_owner_key_named_outside_an_owner_consumer_is_the_handoff_finding(tmp_path):
    """G16b (check-O5): `$$DATABASE_URL_OWNER` is the literal the container's shell expands — but a
    service that does not load `.env.owner` has no such variable after the split, so naming the key
    there is the hand-off finding too (remedy: declare the file)."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  migrate:\n"
        "    env_file:\n"
        "      - .env\n"
        '    command: sh -c "psql $$DATABASE_URL_OWNER -f db/schema.sql"\n',
    )

    result = scan_repo(repo)

    assert [(f.line, f.pattern) for f in result.findings] == [(5, arc.OWNER_HANDOFF_REMEDY)], (
        result.findings
    )


def test_owner_consumer_with_the_escaped_owner_key_in_its_command_is_clean(tmp_path):
    """G16c (check-O5): inside an owner consumer `$$DATABASE_URL_OWNER` reaches the container as the
    literal, the shell expands it from `.env.owner` — no finding; the `$`-interpolated form in the same
    place IS the hand-off (the structural owner-consumer rule never hides it)."""
    repo = tmp_path / "repo"
    consumer = (
        "services:\n"
        "  migrate:\n"
        "    env_file:\n"
        "      - .env\n"
        "      - path: .env.owner\n"
        "        required: false\n"
    )
    _write(
        repo / "compose.yaml",
        consumer + '    command: sh -c "psql $$DATABASE_URL_OWNER -f db/schema.sql"\n',
    )
    assert scan_repo(repo).findings == []

    _write(
        repo / "compose.yaml",
        consumer + '    command: sh -c "psql $DATABASE_URL_OWNER -f db/schema.sql"\n',
    )
    result = scan_repo(repo)
    assert [(f.line, f.pattern) for f in result.findings] == [(7, arc.OWNER_HANDOFF_REMEDY)], (
        result.findings
    )


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


def test_compose_environment_owner_value_is_a_finding_after_the_split(tmp_path):
    """Owner split (D-754): `${DATABASE_URL_OWNER}` is interpolated from the project `.env`,
    which no longer carries the key, so the value would be EMPTY — a finding whose remedy names
    `.env.owner`, `env_file` and reading the key from the environment."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n  api:\n    environment:\n      DATABASE_URL: ${DATABASE_URL_OWNER}\n",
    )

    result = scan_repo(repo)

    (finding,) = result.findings
    assert finding.pattern == arc.OWNER_HANDOFF_REMEDY and finding.line == 4
    for word in (
        ".env.owner",
        "env_file",
        "DATABASE_URL_OWNER",
        "env.py",
        "docker compose run --rm",
    ):
        assert word in finding.pattern


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


def test_run_check_sentence_patterns_carry_no_reaches_suffix(tmp_path):
    """G21 (owner split review, round 1 — check-O6): the two owner-split texts are sentences, so the
    failure line is `<path>:<line> <sentence>` — never `… .env.owner reaches DATABASE_URL`; a label
    pattern in the same run keeps its suffix."""
    clone = _synced_clone(tmp_path)
    _write(clone / "compose.yaml", "services:\n  migrate:\n    command: alembic upgrade head\n")
    _write(
        clone / "alembic" / "env.py",
        "import os\nfrom alembic import context\nurl = os.environ['DATABASE_URL_OWNER']\n",
    )

    with patch.object(arc, "probe_app_role", return_value=[]):
        result = run_check("mydb", clone)

    assert f"alembic/env.py:3 {arc.NO_OWNER_CONSUMER}" in result.failures, result.failures
    assert "compose.yaml:2 compose service named migrate reaches DATABASE_URL" in result.failures
    assert not any(line.endswith(".env.owner reaches DATABASE_URL") for line in result.failures)
    assert not any("there) reaches DATABASE_URL" in line for line in result.failures)


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


def test_migrate_service_owner_interpolation_is_a_finding_after_the_split(tmp_path):
    """Was O18's canonical hand-off. Owner split (D-754): the `DATABASE_URL:` KEY text still never
    counts as the bare-token disqualifier (the `migrate` finding stays suppressed), but the VALUE
    `${DATABASE_URL_OWNER}` is now the one finding — compose interpolates it from the project `.env`,
    which no longer carries the key."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n  migrate:\n    environment:\n      DATABASE_URL: ${DATABASE_URL_OWNER}\n",
    )

    result = scan_repo(repo)

    assert [f.pattern for f in result.findings] == [arc.OWNER_HANDOFF_REMEDY], result.findings


def test_owner_consumer_migrate_service_with_an_owner_env_py_is_clean(tmp_path):
    """G12 (D-754): the check ACCEPTS its own remedy — a `migrate` service declaring `.env.owner`
    (long syntax) whose alembic `env.py` reads `DATABASE_URL_OWNER` yields NO finding. Today's
    scanner reported two on this shape (`compose service named migrate`, `alembic upgrade/downgrade`),
    so without the rule every cutover with a migrate service would refuse."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  app:\n"
        "    env_file:\n"
        "      - .env\n"
        "  migrate:\n"
        "    env_file:\n"
        "      - .env\n"
        "      - path: .env.owner\n"
        "        required: false\n"
        "    command: alembic upgrade head\n",
    )
    _write(
        repo / "alembic" / "env.py",
        "import os\nfrom alembic import context\nurl = os.environ['DATABASE_URL_OWNER']\n",
    )

    result = scan_repo(repo)

    assert result.findings == [], result.findings


def test_owner_env_py_with_no_declaring_service_is_a_finding(tmp_path):
    """G13 (D-754), the mirror: an alembic env that reads `DATABASE_URL_OWNER` while NO compose
    service declares `.env.owner` reads an empty value in every service after the split — one
    finding at the env.py line, BESIDE the two today's scanner already reports for a `migrate`
    service with no owner source (which stay: that service is not an owner consumer)."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  app:\n"
        "    env_file:\n"
        "      - .env\n"
        "  migrate:\n"
        "    env_file:\n"
        "      - .env\n"
        "    command: alembic upgrade head\n",
    )
    _write(
        repo / "alembic" / "env.py",
        "import os\nfrom alembic import context\nurl = os.environ['DATABASE_URL_OWNER']\n",
    )

    result = scan_repo(repo)

    mirror = [f for f in result.findings if f.pattern == arc.NO_OWNER_CONSUMER]
    assert [(f.path, f.line) for f in mirror] == [("alembic/env.py", 3)], result.findings
    others = sorted(f.pattern for f in result.findings if f.pattern != arc.NO_OWNER_CONSUMER)
    assert others == ["alembic upgrade/downgrade", "compose service named migrate"], result.findings


def test_owner_consumer_block_keeps_a_bare_database_url_use_and_the_neighbour_service(tmp_path):
    """G17 (owner split review, rounds 1-2 — check-S1/H2/O1/O3/O9, scaffold-S2/S3): inside an owner
    consumer only a line naming NO bare DATABASE_URL clears — `alembic upgrade head` does, a
    `psql "$$DATABASE_URL"` in the same block is the app role's connection and stays. The block's
    FIRST and LAST body lines are tool lines that clear, and the services on either side carry
    tool lines (no bare DATABASE_URL, so ONLY the range decides them): the line before the block,
    and the KEY line right after it (a flow-style service, so a range widened by ONE at the end
    swallows a finding — a block-style neighbour's key line never carries one). A range moved or
    widened by one or two at either end reds; a filter dropping every line in the file reds too."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n"  # 1
        "  app:\n"  # 2
        "    env_file:\n"  # 3
        "      - .env\n"  # 4
        "    command: alembic upgrade head\n"  # 5 — the line before the block: a non-consumer's tool line
        "  migrate:\n"  # 6
        "    command: alembic upgrade head\n"  # 7 — the block's first body line: clears
        "    healthcheck:\n"  # 8
        '      test: sh -c \'psql "$$DATABASE_URL" -c "select 1"\'\n'  # 9 — stays: the app role's connection
        "    env_file:\n"  # 10
        "      - .env\n"  # 11
        "      - path: .env.owner\n"  # 12
        "        required: false\n"  # 13
        "    entrypoint: alembic upgrade head\n"  # 14 — the block's last body line: clears
        "  worker: {command: npx prisma migrate deploy}\n",  # 15 — the first line outside the block
    )
    _write(
        repo / "alembic" / "env.py",
        "import os\nfrom alembic import context\nurl = os.environ['DATABASE_URL_OWNER']\n",
    )

    result = scan_repo(repo)

    assert sorted((f.line, f.pattern) for f in result.findings) == [
        (5, "alembic upgrade/downgrade"),
        (9, "psql invocation"),
        (15, "prisma migrate/db push"),
    ], result.findings


def test_compose_handoff_is_matched_on_the_raw_line(tmp_path):
    """G26 (owner split review, round 2 — check-O11): a `--flag` or a `${VAR#pat}` before the
    interpolation is not a comment — the module's raw-line rule holds for the hand-off too, so the
    consumer's command interpolating the owner key behind `--dbname` is the finding (the keep-rule
    would otherwise have cleared the psql line: it names no bare DATABASE_URL)."""
    repo = tmp_path / "repo"
    consumer = (
        "services:\n"
        "  migrate:\n"
        "    env_file:\n"
        "      - .env\n"
        "      - path: .env.owner\n"
        "        required: false\n"
    )
    for command in (
        '    command: sh -c "psql --dbname $DATABASE_URL_OWNER -f db/schema.sql"\n',
        '    command: sh -c "x=${HOME#/}; psql $DATABASE_URL_OWNER -f db/schema.sql"\n',
    ):
        _write(repo / "compose.yaml", consumer + command)
        result = scan_repo(repo)
        assert [(f.line, f.pattern) for f in result.findings] == [(7, arc.OWNER_HANDOFF_REMEDY)], (
            command,
            result.findings,
        )


@pytest.mark.parametrize(
    ("dollars", "handoff"),
    [("$", True), ("$$", False), ("$$$", True), ("$$$$", False)],
)
def test_compose_handoff_counts_the_run_of_dollars(tmp_path, dollars, handoff):
    """G27 (check-O12, scaffold-S5/H1): compose reads `$$` as ONE literal dollar and the next `$`
    starts an interpolation — an odd run interpolates (the hand-off), an even run reaches the
    container's shell as a literal (clears inside an owner consumer)."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  migrate:\n"
        "    env_file:\n"
        "      - .env\n"
        "      - path: .env.owner\n"
        "        required: false\n"
        f'    command: sh -c "psql {dollars}DATABASE_URL_OWNER -f db/schema.sql"\n',
    )

    result = scan_repo(repo)

    expected = [(7, arc.OWNER_HANDOFF_REMEDY)] if handoff else []
    assert [(f.line, f.pattern) for f in result.findings] == expected, (dollars, result.findings)


def test_compose_handoff_is_reported_once_per_service(tmp_path):
    """G28 (check-O13): a folded `environment:` value puts the key on one line and the interpolation
    on the next — the structural scan reports the key line, the line scan sees the value line; ONE
    finding for the one hand-off (the remedy is the service's), never two."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  api:\n"
        "    environment:\n"
        "      DATABASE_URL: >-\n"
        "        ${DATABASE_URL_OWNER}\n"
        '    command: sh -c "psql $DATABASE_URL_OWNER -c select"\n',
    )

    result = scan_repo(repo)

    assert [f.pattern for f in result.findings] == [arc.OWNER_HANDOFF_REMEDY], result.findings


_CONSUMER_HEAD = (
    "services:\n"
    "  migrate:\n"
    "    env_file:\n"
    "      - .env\n"
    "      - path: .env.owner\n"
    "        required: false\n"
)


@pytest.mark.parametrize(
    ("compose", "expected"),
    [
        # the anchor on the tool line itself
        (
            _CONSUMER_HEAD + "    command: &c alembic upgrade head\n  app:\n    command: *c\n",
            [(7, "alembic upgrade/downgrade")],
        ),
        # a folded anchored scalar: the anchor on the key line, the tool text on the next
        (
            _CONSUMER_HEAD
            + "    command: &c >-\n      alembic upgrade head\n  app:\n    command: *c\n",
            [(8, "alembic upgrade/downgrade")],
        ),
        # a service-level anchor merged into a non-consumer
        (
            "services:\n"
            "  migrate: &base\n"
            "    env_file:\n"
            "      - .env\n"
            "      - path: .env.owner\n"
            "        required: false\n"
            "    command: alembic upgrade head\n"
            "  app:\n"
            "    <<: *base\n"
            "    env_file:\n"
            "      - .env\n",
            [(7, "alembic upgrade/downgrade")],
        ),
        # an aliased owner-key use: the non-consumer gets a literal it cannot expand — the hand-off
        (
            _CONSUMER_HEAD
            + '    command: &c sh -c "psql $$DATABASE_URL_OWNER -f x.sql"\n  app:\n    command: *c\n',
            [(7, arc.OWNER_HANDOFF_REMEDY)],
        ),
    ],
)
def test_owner_consumer_sharing_an_anchor_is_scanned_like_any_service(tmp_path, compose, expected):
    """G29 (check-O9, rounds 2-3): the range filter reads text, not the resolved YAML graph — a
    declaring block that defines an anchor aliased OUTSIDE it (on the tool line, on a folded key
    line, or on the service itself merged with `<<:`) is no suppression range at all: the aliasing
    service runs those values, so the block's tool lines are findings and its owner-key use the
    hand-off (fail closed)."""
    repo = tmp_path / "repo"
    _write(repo / "compose.yaml", compose)

    assert [(f.line, f.pattern) for f in scan_repo(repo).findings] == expected, scan_repo(
        repo
    ).findings


def test_owner_consumer_anchor_name_ending_in_a_dash_is_still_shared(tmp_path):
    """G29c (owner split review, round 4 — check-O16): a YAML anchor name may end in `-`, where a
    `\b` after the alias would not match — the alias is read to where an anchor name ends, so the
    block is still no suppression range."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        _CONSUMER_HEAD + "    command: &cmd- alembic upgrade head\n  app:\n    command: *cmd-\n",
    )

    assert [(f.line, f.pattern) for f in scan_repo(repo).findings] == [
        (7, "alembic upgrade/downgrade")
    ]


def test_two_owner_consumers_sharing_an_anchored_env_file_both_clear(tmp_path):
    """G29d (check-O17): an anchor aliased by ANOTHER declaring service is shared between two
    consumers that both load `.env.owner` — neither is scanned as a non-consumer, both clear."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  migrate:\n"
        "    env_file: &owner_files\n"
        "      - .env\n"
        "      - path: .env.owner\n"
        "        required: false\n"
        "    command: alembic upgrade head\n"
        "  jobs:\n"
        "    env_file: *owner_files\n"
        "    command: alembic upgrade head\n",
    )

    assert scan_repo(repo).findings == []


def test_shared_anchor_counts_through_a_disqualified_consumer(tmp_path):
    """G29e (owner split review, round 5 — check-O18): declaring `migrate` is `&a`; declaring `jobs`
    merges `<<: *a` and is `&b`; the non-consumer `app` merges `<<: *b` and so runs BOTH their
    commands. `jobs` is disqualified by `app`'s alias; once it is, its `*a` is outside every
    consumer and `migrate` is disqualified too — a share counts through any number of hops."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  migrate: &a\n"
        "    env_file:\n"
        "      - .env\n"
        "      - path: .env.owner\n"
        "        required: false\n"
        "    command: alembic upgrade head\n"  # 7
        "  jobs: &b\n"
        "    <<: *a\n"
        "    command: npx prisma migrate deploy\n"  # 10
        "  app:\n"
        "    <<: *b\n"
        "    env_file:\n"
        "      - .env\n",
    )

    assert sorted((f.line, f.pattern) for f in scan_repo(repo).findings) == [
        (7, "alembic upgrade/downgrade"),
        (10, "prisma migrate/db push"),
    ]


def test_owner_consumer_anchor_aliased_only_inside_its_block_still_clears(tmp_path):
    """G29b (the mirror of G29): an anchor aliased within the SAME service is that service's own
    value — the block stays the consumer and clears like any other."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        _CONSUMER_HEAD
        + "    command: &c alembic upgrade head\n"
        + "    healthcheck:\n"
        + "      test: *c\n"
        + "  app:\n"
        + "    command: echo hi\n",
    )

    assert scan_repo(repo).findings == []


@pytest.mark.parametrize(
    "env_file_block",
    [
        "    env_file: .env.owner\n",
        "    env_file:\n      - .env\n      - .env.owner\n",
        "    env_file:\n      - .env\n      - ./.env.owner\n",
        "    env_file:\n      - .env\n      - path: .env.owner\n        required: false\n",
        "    env_file:\n      - .env\n      - path: ./.env.owner\n",
    ],
)
def test_owner_consumer_declaration_is_recognised_in_every_compose_spelling(
    tmp_path, env_file_block
):
    """G18 (check-O3/O7; core/45: a guard proven by one spelling is banned): the scalar form, the list
    string, the long syntax, and `./`-prefixed paths all name the same file relative to the project
    directory — each makes the service the owner consumer (G12's shape stays clean)."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n  migrate:\n" + env_file_block + "    command: alembic upgrade head\n",
    )
    _write(
        repo / "alembic" / "env.py",
        "import os\nfrom alembic import context\nurl = os.environ['DATABASE_URL_OWNER']\n",
    )

    assert scan_repo(repo).findings == [], env_file_block


def test_owner_consumer_declaration_never_matches_another_file(tmp_path):
    """G18b (check-O7, the mirror of G18): a parent-relative or absolute path is a DIFFERENT file —
    the service is not the consumer, G13's three findings fire."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n  migrate:\n    env_file:\n      - ../.env.owner\n    command: alembic upgrade head\n",
    )
    _write(
        repo / "alembic" / "env.py",
        "import os\nfrom alembic import context\nurl = os.environ['DATABASE_URL_OWNER']\n",
    )

    patterns = sorted(f.pattern for f in scan_repo(repo).findings)
    assert patterns == sorted(
        [arc.NO_OWNER_CONSUMER, "alembic upgrade/downgrade", "compose service named migrate"]
    ), patterns


def test_mirror_reports_every_owner_site_of_the_alembic_env(tmp_path):
    """G19 (check-O3 mutant 6): an env.py naming the owner key on two live lines is two mirror
    findings, one per site — never only the first."""
    repo = tmp_path / "repo"
    _write(repo / "compose.yaml", "services:\n  app:\n    env_file:\n      - .env\n")
    _write(
        repo / "alembic" / "env.py",
        "import os\nfrom alembic import context\n"
        "url = os.environ['DATABASE_URL_OWNER']\n"
        "fallback = os.getenv('DATABASE_URL_OWNER')\n",
    )

    mirror = [
        (f.path, f.line) for f in scan_repo(repo).findings if f.pattern == arc.NO_OWNER_CONSUMER
    ]
    assert mirror == [("alembic/env.py", 3), ("alembic/env.py", 4)], mirror


def test_mirror_stays_silent_when_the_compose_file_does_not_parse(tmp_path):
    """G20 (check-O8): an unparseable compose file is its own finding and says nothing about which
    services declare `.env.owner` — the mirror never asserts what cannot be known from it."""
    repo = tmp_path / "repo"
    _write(repo / "compose.yaml", "services:\n  app: [\n")
    _write(
        repo / "alembic" / "env.py",
        "import os\nfrom alembic import context\nurl = os.environ['DATABASE_URL_OWNER']\n",
    )

    patterns = [f.pattern for f in scan_repo(repo).findings]
    assert patterns == ["compose file unparseable"], patterns


def test_handoff_scan_stays_silent_when_the_compose_file_does_not_parse(tmp_path):
    """G30 (the Finish review, check-S1): an unparseable compose file is its own finding; the raw-text
    hand-off scan never adds `OWNER_HANDOFF_REMEDY` on top of it — the file names no service that
    could carry the remedy, so the finding would assert what cannot be known (G20's rule)."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n  migrate: [\n    command: sh -c 'psql $DATABASE_URL_OWNER -f x.sql'\n",
    )

    patterns = [f.pattern for f in scan_repo(repo).findings]
    assert patterns == ["compose file unparseable"], patterns


def test_mirror_counts_a_lowercase_settings_attribute_as_an_owner_site(tmp_path):
    """G22 (check-O10, scaffold-S4 — the asymmetry pinned on purpose): `settings.database_url_owner`
    reads the same environment variable through pydantic-settings, so it is an owner site for the
    mirror; the compose-side classifier stays case-sensitive because a shell variable name is."""
    repo = tmp_path / "repo"
    _write(repo / "compose.yaml", "services:\n  app:\n    env_file:\n      - .env\n")
    _write(
        repo / "alembic" / "env.py",
        "from alembic import context\nfrom app.config import settings\nurl = settings.database_url_owner\n",
    )

    mirror = [
        (f.path, f.line) for f in scan_repo(repo).findings if f.pattern == arc.NO_OWNER_CONSUMER
    ]
    assert mirror == [("alembic/env.py", 3)], mirror


def test_owner_consumer_environment_handoff_is_reported_once(tmp_path):
    """G25 (brief hunt 6d): an owner consumer whose `environment:` ALSO interpolates the owner key is
    the hand-off finding — the block rule never hides it, and the structural and line-level scans
    report the one line ONCE."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  migrate:\n"
        "    env_file:\n"
        "      - .env\n"
        "      - path: .env.owner\n"
        "        required: false\n"
        "    environment:\n"
        "      DATABASE_URL: ${DATABASE_URL_OWNER}\n"
        "    command: alembic upgrade head\n",
    )

    result = scan_repo(repo)

    assert [(f.line, f.pattern) for f in result.findings] == [(8, arc.OWNER_HANDOFF_REMEDY)], (
        result.findings
    )


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


def test_migrate_list_form_owner_handoff_is_a_finding_after_the_split(tmp_path):
    """Was O28. The `DATABASE_URL=` key text still never counts as a bare-token use (the `migrate`
    finding stays suppressed); the list-form VALUE `${DATABASE_URL_OWNER}` is the one finding after
    the owner split (D-754)."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n  migrate:\n    environment:\n      - DATABASE_URL=${DATABASE_URL_OWNER}\n",
    )

    result = scan_repo(repo)

    assert [f.pattern for f in result.findings] == [arc.OWNER_HANDOFF_REMEDY], result.findings


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


# ── Fixup D7 (whole-plan validation — the O30 residue) ─────────────────────── #


@pytest.mark.parametrize(
    "null_spelling",
    ["~", "null", "Null", "NULL", "  # inherit"],
)
def test_migrate_yaml_null_database_url_still_counts_as_bare_whatever_the_spelling(
    tmp_path, null_spelling
):
    """O30 (fail-open): YAML accepts several null spellings (`~`, `null`, `Null`,
    `NULL`, an empty scalar — optionally followed by a `# comment`) and PyYAML
    resolves every one of them to the SAME Python `None`. The r3 fix for O27 only
    recognised a textually EMPTY value, so a `DATABASE_URL: ~` (etc.) sibling to
    `DATABASE_URL_OWNER: ${DATABASE_URL_OWNER}` still falsely suppressed the
    migrate finding while the container silently inherits the host DATABASE_URL."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n"
        "  migrate:\n"
        "    environment:\n"
        f"      DATABASE_URL: {null_spelling}\n"
        "      DATABASE_URL_OWNER: ${DATABASE_URL_OWNER}\n",
    )

    result = scan_repo(repo)

    assert any(f.pattern == "compose service named migrate" for f in result.findings)


def test_migrate_real_owner_reference_still_clears_the_migrate_finding_after_d7(tmp_path):
    """The D7 fix must not regress O18's rule: a REAL owner reference (not a null) still clears
    the `migrate` finding — after the owner split (D-754) the VALUE itself is the one finding."""
    repo = tmp_path / "repo"
    _write(
        repo / "compose.yaml",
        "services:\n  migrate:\n    environment:\n      DATABASE_URL: ${DATABASE_URL_OWNER}\n",
    )

    result = scan_repo(repo)

    assert "compose service named migrate" not in {f.pattern for f in result.findings}
    assert [f.pattern for f in result.findings] == [arc.OWNER_HANDOFF_REMEDY], result.findings


# ── Fixup D7 (whole-plan validation — O2, S1, S2) ──────────────────────────── #


@pytest.mark.parametrize(
    ("rel", "comment"),
    [
        ("entrypoint.sh", '# psql "$DATABASE_URL" -f db/schema.sql'),
        ("app/x.py", '    # psql "$DATABASE_URL" -f db/schema.sql'),
        ("app/x.py", "-- CREATE TABLE t (id int);"),
        ("web/x.ts", '  // psql "$DATABASE_URL" -f db/schema.sql'),
        ("web/x.ts", "-- CREATE TABLE t (id int);"),
    ],
)
def test_whole_line_comment_is_inert_but_the_same_code_line_is_found(tmp_path, rel, comment):
    """O2: a line whose stripped text starts with its file's comment marker never runs,
    so it is not scanned; the same text as code (marker removed) is still a finding."""
    repo = tmp_path / "repo"
    _write(repo / rel, comment + "\n")
    assert scan_repo(repo).findings == []

    code = comment.strip().removeprefix("#").removeprefix("//").removeprefix("--").strip()
    _write(repo / rel, code + "\n")
    assert len(scan_repo(repo).findings) == 1


def test_leading_double_dash_in_a_shell_file_is_live_code(tmp_path):
    """The mirror of O2: in a shell-family file a line starting ``--`` is a continued
    command's argument, never a comment — it must still be scanned."""
    repo = tmp_path / "repo"
    _write(
        repo / "entrypoint.sh",
        'psql "$DATABASE_URL" \\\n  --command "CREATE TABLE t (id int)"\n',
    )
    assert [f.pattern for f in scan_repo(repo).findings] == ["psql invocation", "runtime DDL"]


def test_alembic_env_comment_line_is_inert(tmp_path):
    repo = tmp_path / "repo"
    _write(
        repo / "migrations" / "env.py",
        "from alembic import context\n# url = os.environ['DATABASE_URL']\n",
    )
    assert scan_repo(repo).findings == []


def test_synced_enforcement_tree_is_not_walked_but_a_same_named_dir_elsewhere_is(tmp_path):
    repo = tmp_path / "repo"
    _write(repo / "scripts" / "enforcement" / "check.py", 'sql = "CREATE TABLE t (id int)"\n')
    _write(repo / "app" / "enforcement" / "x.py", 'sql = "CREATE TABLE t (id int)"\n')
    result = scan_repo(repo)
    assert [f.path for f in result.findings] == ["app/enforcement/x.py"]


def test_skipped_enforcement_dir_matches_the_synced_manifest():
    """The restated path must stay the manifest's ENFORCEMENT_DIR."""
    import importlib.util

    manifest_path = Path(__file__).resolve().parents[1] / "scripts" / "fabrik_synced_manifest.py"
    spec = importlib.util.spec_from_file_location("_manifest_under_test", manifest_path)
    assert spec is not None and spec.loader is not None
    manifest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(manifest)
    assert {manifest.ENFORCEMENT_DIR} == arc._SKIP_REL_DIRS


def test_cli_app_role_check_malformed_yaml_exits_1(tmp_path):
    """S1: a YAML syntax error is a ✗ line and exit 1, never an uncaught exception."""
    from click.testing import CliRunner

    from fabrik.cli import cli

    spec_path = tmp_path / "svc.yaml"
    spec_path.write_text("id: [unclosed\n")

    result = CliRunner().invoke(cli, ["app-role-check", "--spec", str(spec_path)])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit), result.exception
    assert "✗ spec is not valid YAML: " in result.output


@pytest.mark.parametrize("value", [True, 1, ["a"]])
def test_db_name_refuses_a_non_string_depends_postgres(value):
    """S2: YAML `true` must never become database "True"."""
    with pytest.raises(SpecResolutionError, match="depends.postgres must be a string"):
        _db_name_for_spec({"id": "x", "depends": {"postgres": value}})


def test_db_name_string_depends_postgres_still_wins():
    assert _db_name_for_spec({"id": "x", "depends": {"postgres": "x_db"}}) == "x_db"


# ── Docstrings never execute, so their prose is not a finding ───────────────── #

_DOC_DDL = "ALTER TABLE t NO FORCE ROW LEVEL SECURITY"


@pytest.mark.parametrize(
    "content",
    [
        f'"""Module doc.\n\nThree escapes: ``{_DOC_DDL}``.\n"""\nx = 1\n',
        f'def guard():\n    """Refuse a connection that could run\n    {_DOC_DDL}."""\n    return 1\n',
        f'class Guard:\n    """{_DOC_DDL}"""\n\n    def f(self):\n        return 1\n',
    ],
    ids=["module", "function", "class"],
)
def test_a_docstring_that_names_ddl_is_not_a_finding(tmp_path, content):
    repo = tmp_path / "repo"
    _write(repo / "src/guard.py", content)

    assert scan_repo(repo).findings == []


@pytest.mark.parametrize(
    "content",
    [
        f'"""Doc."""\nSQL = "{_DOC_DDL}"\n',
        f'def f(): """doc"""; run("{_DOC_DDL}")\n',
        f'def f():\n    """doc"""\n    return "{_DOC_DDL}"\n',
        f'def broken(:\n    """{_DOC_DDL}"""\n',
        f'def f():\n    x = 1\n    y = 2\n    "{_DOC_DDL}"\n    return x + y\n',
    ],
    ids=[
        "string-constant",
        "same-line-code",
        "code-after-docstring",
        "unparseable-file",
        "later-bare-string-is-not-a-docstring",
    ],
)
def test_ddl_outside_a_real_docstring_is_still_a_finding(tmp_path, content):
    repo = tmp_path / "repo"
    _write(repo / "src/runtime.py", content)

    assert [f.pattern for f in scan_repo(repo).findings] == ["runtime DDL"]


@pytest.mark.parametrize("exc", [RecursionError, MemoryError])
def test_a_parser_blowup_scans_the_file_whole_instead_of_crashing(tmp_path, monkeypatch, exc):
    repo = tmp_path / "repo"
    _write(repo / "src/deep.py", f'"""{_DOC_DDL}"""\n')

    def blow(_text):
        raise exc("too deep")

    monkeypatch.setattr(arc, "_parse_python", blow)

    assert [f.pattern for f in scan_repo(repo).findings] == ["runtime DDL"]


def test_a_line_break_python_does_not_count_voids_the_exemption(tmp_path):
    """str.splitlines() breaks on \\x0c; the parser does not. Numbering would drift and the
    exemption land on a later line — here a def header whose default argument runs DDL."""
    content = (
        'def a():\n    """doc\x0cmore"""\n    return 1\n\n\n'
        f'def b(q="{_DOC_DDL}"):\n    """doc"""\n    return q\n'
    )
    repo = tmp_path / "repo"
    _write(repo / "src/drift.py", content)

    assert [f.pattern for f in scan_repo(repo).findings] == ["runtime DDL"]


def test_owner_handoff_remedy_env_file_example_keeps_both_files_optional():
    """W-e80e79f0: the env_file the remedy tells a project to write must not make `.env` required.
    The short form `[.env, ...]` fails `docker compose config` on a fresh checkout with no .env
    (the D-931/D-938 class); every entry is long form with `required: false`."""
    import re

    import yaml

    m = re.search(r"env_file (\[.*?\}\])", arc.OWNER_HANDOFF_REMEDY)
    assert m, arc.OWNER_HANDOFF_REMEDY
    entries = yaml.safe_load(m.group(1))
    assert entries == [
        {"path": ".env", "required": False},
        {"path": ".env.owner", "required": False},
    ], entries
