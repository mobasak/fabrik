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
    assert TEST_DATABASE_URL in wf and TEST_DATABASE_URL in local
    assert "+asyncpg" not in wf and "+asyncpg" not in local
    assert "postgres:16" in wf  # no pgvector requested -> plain image


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
    assert "\npytest -q\n" in local  # verbatim, resolved via PATH


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
