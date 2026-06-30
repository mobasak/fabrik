"""Tests for ``scripts/enforcement/check_spec_db_match.py`` (deploy-readiness-gaps
Phase 1c): the spec <-> project DB-name consistency gate.

The check compares each ``needs_database`` spec's resolved DB name
(``depends.postgres`` or the derived spec-id) against the project's own
``PG_DATABASE`` / ``DATABASE_URL`` in its ``.env.example`` — the drift class that
left calendar pointed at an empty/wrong DB.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "enforcement" / "check_spec_db_match.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("check_spec_db_match", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _wire(monkeypatch, tmp_path: Path, spec_yaml: str, env_text: str | None, *, project="foo"):
    """Build a fake specs/ + /opt/<project> tree and point the module at it."""
    m = _load()
    specs = tmp_path / "specs" / "services"
    specs.mkdir(parents=True)
    (specs / f"{project}.yaml").write_text(spec_yaml)
    opt = tmp_path / "opt"
    (opt / project).mkdir(parents=True)
    if env_text is not None:
        (opt / project / ".env.example").write_text(env_text)
    monkeypatch.setattr(m, "SPECS_DIR", specs)
    monkeypatch.setattr(m, "OPT_ROOT", opt)
    return m


def test_passes_when_spec_matches_project_env(tmp_path, monkeypatch):
    m = _wire(
        monkeypatch,
        tmp_path,
        "id: foo\nshape:\n  needs_database: true\ndepends:\n  postgres: foo_db\n",
        "PG_DATABASE=foo_db\n",
    )
    assert m.main() == 0


def test_passes_via_database_url(tmp_path, monkeypatch):
    m = _wire(
        monkeypatch,
        tmp_path,
        "id: foo\nshape:\n  needs_database: true\ndepends:\n  postgres: foo_db\n",
        "DATABASE_URL=postgresql://u:p@postgres-main:5432/foo_db?sslmode=disable\n",
    )
    assert m.main() == 0


def test_passes_on_derived_name_when_depends_absent(tmp_path, monkeypatch):
    # No depends.postgres → resolves to the derived spec-id name; project matches.
    m = _wire(
        monkeypatch,
        tmp_path,
        "id: my-svc\nshape:\n  needs_database: true\n",
        "PG_DATABASE=my_svc\n",
        project="my-svc",
    )
    assert m.main() == 0


def test_fails_when_drift_detected(tmp_path, monkeypatch):
    m = _wire(
        monkeypatch,
        tmp_path,
        "id: foo\nshape:\n  needs_database: true\ndepends:\n  postgres: foo_db\n",
        "PG_DATABASE=other_db\n",
    )
    assert m.main() == 1


def test_skips_spec_without_project_env(tmp_path, monkeypatch):
    # needs_database spec but no project .env to compare → nothing to assert, pass.
    m = _wire(
        monkeypatch,
        tmp_path,
        "id: foo\nshape:\n  needs_database: true\ndepends:\n  postgres: foo_db\n",
        None,
    )
    assert m.main() == 0


def test_skips_spec_without_needs_database(tmp_path, monkeypatch):
    m = _wire(
        monkeypatch,
        tmp_path,
        "id: foo\nshape:\n  needs_database: false\ndepends:\n  postgres: foo_db\n",
        "PG_DATABASE=wrong_db\n",  # would mismatch, but needs_database=false → skipped
    )
    assert m.main() == 0


def test_skips_cleanly_when_no_specs_dir(tmp_path, monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "SPECS_DIR", tmp_path / "nonexistent" / "services")
    assert m.main() == 0
