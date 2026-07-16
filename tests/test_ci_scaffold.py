"""Tests for src/fabrik/ci_scaffold.py — the one-source CI generator.

The whole point is that `ci.yml` and `ci_local.sh` cannot drift, because they render
from the same CiConfig. These tests pin the parity invariants that drift caused the
original trade-intelligence failures: same PG image, the PLAIN (non-+asyncpg) URL,
the same full-suite test command.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from fabrik.ci_scaffold import (
    TEST_DATABASE_URL,
    CiConfig,
    ci_files,
    render_ci_local,
    render_ci_workflow,
)


def test_db_image_matches_between_workflow_and_local():
    cfg = CiConfig(needs_database=True, db_extensions=("pgvector",))
    wf = render_ci_workflow(cfg)
    local = render_ci_local(cfg)
    assert "pgvector/pgvector:pg16" in wf
    assert "pgvector/pgvector:pg16" in local  # parity: same image both sides


def test_plain_url_not_asyncpg_both_sides():
    # failure #1 was a +asyncpg local URL vs plain CI URL — both renders must use plain
    cfg = CiConfig(needs_database=True)
    wf = render_ci_workflow(cfg)
    local = render_ci_local(cfg)
    assert TEST_DATABASE_URL in wf  # CI runner is clean -> the fixed :5432 URL
    # local binds a FREE host port (no clash with a dev Postgres) but the URL stays plain libpq
    assert "postgresql://postgres:postgres@localhost:$PGPORT/postgres" in local
    assert "+asyncpg" not in wf and "+asyncpg" not in local
    assert "postgres:16" in wf  # no pgvector requested -> plain image


def test_local_postgres_uses_a_free_host_port():
    # A hardcoded -p 5432:5432 collides with a dev/shared Postgres on the box and fails the replica
    # for no real reason. Let docker assign a free host port, then read it back.
    local = render_ci_local(CiConfig(needs_database=True))
    assert "-p 127.0.0.1::5432" in local  # docker picks a free host port
    assert 'docker port "$CID" 5432/tcp' in local  # resolve the assigned port
    assert "-p 5432:5432" not in local


def test_same_test_command_both_sides():
    cfg = CiConfig(test_cmd="python -m pytest -q")
    wf = render_ci_workflow(cfg)
    local = render_ci_local(cfg)
    assert "python -m pytest -q" in wf
    # local prepends the fresh venv to PATH then runs the command verbatim
    assert 'export PATH="$VENV/bin:$PATH"' in local
    assert "python -m pytest -q" in local


def test_local_runs_bare_test_cmd_via_venv_path():
    # a non-`python ...` test_cmd (e.g. "pytest -q") must still run from the venv, not
    # the system — the PATH prepend guarantees it (finding E regression).
    local = render_ci_local(CiConfig(test_cmd="pytest -q"))
    assert 'export PATH="$VENV/bin:$PATH"' in local
    # The bare cmd still runs first via PATH; it is now wrapped so "no tests collected"
    # (exit 5) doesn't fail the run, but genuine failures still propagate (exit "$c").
    assert "\npytest -q ||" in local
    assert 'exit "$c"' in local


def test_ruff_always_installed_even_with_no_test_deps():
    # finding G: `ruff check .` always runs, so ruff must always be installed —
    # even when extra_test_deps is empty.
    for cfg in (CiConfig(extra_test_deps=()), CiConfig()):
        local = render_ci_local(cfg)
        wf = render_ci_workflow(cfg)
        assert "ruff check ." in local and "install --quiet ruff" in local
        assert "ruff check ." in wf and "pip install ruff" in wf


def test_pg_readiness_wait_is_bounded():
    # finding D: an unbounded `until pg_isready` hangs forever if the container dies /
    # docker is missing. The wait must be bounded and fail cleanly.
    local = render_ci_local(CiConfig(needs_database=True))
    assert "until docker exec" not in local  # no unbounded loop
    assert "seq 1 60" in local  # bounded retries
    assert "not ready after 60s" in local  # clean failure message
    assert "command -v docker" in local  # fail fast if docker absent


def test_no_database_no_postgres_service():
    cfg = CiConfig(needs_database=False)
    wf = render_ci_workflow(cfg)
    local = render_ci_local(cfg)
    assert "postgres" not in wf.lower()
    assert "docker run" not in local
    assert "TEST_DATABASE_URL" not in wf


def test_web_job_only_when_requested():
    assert "web (type-check" not in render_ci_workflow(CiConfig())
    assert "web (type-check" in render_ci_workflow(CiConfig(needs_web=True))


def test_ci_files_returns_both_paths():
    files = ci_files(CiConfig(needs_database=True))
    assert set(files) == {".github/workflows/ci.yml", "scripts/ci_local.sh"}
    assert files["scripts/ci_local.sh"].startswith("#!/usr/bin/env bash")


def test_local_script_is_valid_bash():
    # the generated script must at least parse under `bash -n` (catches the exec-name
    # quoting bug where the whole "python -m pytest -q" was one quoted token)
    if not shutil.which("bash"):
        pytest.skip("bash not available")
    for cfg in (CiConfig(needs_database=True, db_extensions=("pgvector",)), CiConfig()):
        script = render_ci_local(cfg)
        proc = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True)
        assert proc.returncode == 0, f"bash -n rejected the script: {proc.stderr}\n{script}"


def test_scaffold_write_ci_files_emits_both(tmp_path):
    from fabrik.scaffold import _write_ci_files

    _write_ci_files(tmp_path, needs_database=True)
    ci = tmp_path / ".github" / "workflows" / "ci.yml"
    local = tmp_path / "scripts" / "ci_local.sh"
    assert ci.exists() and local.exists()
    assert local.stat().st_mode & 0o111  # executable
    assert "python -m pytest" in ci.read_text()


def test_workflow_is_valid_yaml():
    yaml = pytest.importorskip("yaml")
    doc = yaml.safe_load(render_ci_workflow(CiConfig(needs_database=True, needs_web=True)))
    assert "jobs" in doc
    assert "python" in doc["jobs"]
    assert "web" in doc["jobs"]


def test_ruff_is_a_ratchet_not_raw_check():
    # Debt-tolerant: the ruff step reads the tracked baseline and fails only on a RISE,
    # so backfilling CI onto a repo with existing lint debt doesn't red the build.
    for text in (render_ci_workflow(CiConfig()), render_ci_local(CiConfig())):
        assert ".fabrik/lint-baseline.json" in text
        assert '[ "$n" -le "$b" ]' in text  # pass while count <= baseline


def test_install_falls_back_to_pyproject_when_no_requirements():
    # A project may declare deps in pyproject.toml instead of requirements.txt; CI must
    # install either, or the install step reds every pyproject-only repo.
    for text in (render_ci_workflow(CiConfig()), render_ci_local(CiConfig())):
        assert "-e ." in text  # editable install of the pyproject project
        assert "pyproject.toml" in text
        assert "requirements.txt" in text  # still preferred when present


def test_pytest_tolerates_no_tests_collected_only():
    # "no tests collected" (pytest exit 5) must not fail the build; any real failure must.
    wf = render_ci_workflow(CiConfig(test_cmd="python -m pytest -q"))
    assert '[ "$c" -eq 5 ]' in wf
    assert 'exit "$c"' in wf  # genuine failures still propagate


def test_ruff_is_version_pinned():
    # Unpinned ruff = a new release ships new rules = the ratchet reds a repo with zero code change.
    # Both the workflow and the local replica must pin the exact version.
    from fabrik.ci_scaffold import RUFF_VERSION

    assert RUFF_VERSION and RUFF_VERSION[0].isdigit()
    for text in (render_ci_workflow(CiConfig()), render_ci_local(CiConfig())):
        assert f"ruff=={RUFF_VERSION}" in text


def test_ruff_count_uses_exit_zero():
    # ruff exits 1 when it finds errors; without --exit-zero the count pipeline "fails" under
    # pipefail and the `|| echo 0` fallback appends "0" to the real count (3 -> "30"). --exit-zero
    # makes ruff return 0 so we get the COUNT, not its verdict.
    for text in (render_ci_workflow(CiConfig()), render_ci_local(CiConfig())):
        assert "ruff check . --exit-zero --output-format=json" in text


def test_install_pulls_dev_test_extras():
    # A project's test deps (pytest-httpx, pytest-mock) often live in [project.optional-dependencies]
    # dev/test — `pip install -e .` misses them and tests fail to collect. Install the extras.
    for text in (render_ci_workflow(CiConfig()), render_ci_local(CiConfig())):
        assert '-e ".[dev,test]"' in text
