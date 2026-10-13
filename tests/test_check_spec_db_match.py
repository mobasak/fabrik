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


def test_a_named_dependency_with_its_flag_off_is_warned_not_skipped(tmp_path, monkeypatch, capsys):
    """fleet 01M4F7NVDZ: the check `continue`d on a falsy `needs_database` BEFORE reading `depends`,
    so a spec naming a store its registrar will never create was green at commit while `fabrik
    apply` warns on it at deploy. The warning is apply's own `depends_contradiction` clause, so the
    two readers cannot disagree; warn-only (exit 0)."""
    m = _wire(
        monkeypatch,
        tmp_path,
        "id: foo\nshape:\n  needs_database: false\ndepends:\n  postgres: foo_db\n"
        "  postgres_seed: seed.sql\n  redis: '3'\n",
        None,
    )
    assert m.main() == 0
    out = capsys.readouterr().out
    assert "⚠ foo: depends.postgres=foo_db, depends.postgres_seed=seed.sql names a store" in out
    assert "⚠ foo: depends.redis=3 names a store this registrar will NOT create" in out
    assert "false or absent" in out


def test_an_absent_shape_is_a_contradiction_too_and_odd_shapes_never_crash(
    tmp_path, monkeypatch, capsys
):
    """No `shape:` block at all is `absent` (apply reads raw YAML); a list `depends` or a scalar
    `shape` is not a mapping and must not crash the whole check (review A-O7/A-S3)."""
    m = _wire(monkeypatch, tmp_path, "id: foo\ndepends:\n  postgres: foo_db\n", None)
    assert m.main() == 0
    assert "⚠ foo: depends.postgres=foo_db" in capsys.readouterr().out
    for odd in (
        "id: foo\nshape: true\n",
        "id: foo\nshape:\n  needs_database: true\ndepends: [x]\n",
    ):
        m = _wire(monkeypatch, tmp_path / str(len(odd)), odd, "PG_DATABASE=foo\n")
        assert m.main() == 0


def test_a_drift_prints_before_the_contradictions_and_quiet_hides_the_green_summary(
    tmp_path, monkeypatch, capsys
):
    """Review A-O1: the gate shows the first lines of a red row, so the blocking drift comes first;
    A-O5: `--quiet` (how the gate calls it) prints nothing on a clean run."""
    m = _wire(
        monkeypatch,
        tmp_path,
        "id: foo\nshape:\n  needs_database: true\n  needs_cache: false\n"
        "depends:\n  postgres: foo_db\n  redis: '1'\n",
        "PG_DATABASE=other\n",
    )
    assert m.main() == 1
    out = capsys.readouterr().out
    assert out.index("DRIFT") < out.index("⚠")
    m = _wire(
        monkeypatch,
        tmp_path / "q",
        "id: foo\nshape:\n  needs_database: true\ndepends:\n  postgres: foo_db\n",
        "PG_DATABASE=foo_db\n",
    )
    monkeypatch.setattr("sys.argv", ["check_spec_db_match.py", "--quiet"])
    assert m.main() == 0
    assert capsys.readouterr().out == ""


def test_a_name_that_differs_after_a_hyphen_is_drift_and_is_quoted_whole(
    tmp_path, monkeypatch, capsys
):
    """whatsapp-agent 01M4SES972: the value was read through [A-Za-z0-9_]+, so `foo_db-x`
    read as `foo_db` and PASSED, and a drift report quoted a prefix nobody wrote."""
    spec = "id: foo\nshape:\n  needs_database: true\ndepends:\n  postgres: foo_db\n"
    for env in (
        "PG_DATABASE=foo_db-x\n",
        'POSTGRES_DB="foo_db-x"\n',
        "DATABASE_URL=postgresql://u:p@postgres-main:5432/foo_db-x?sslmode=disable\n",
        "DATABASE_URL=postgresql+asyncpg://u:p@h:5432/foo_db.x\n",
    ):
        m = _wire(monkeypatch, tmp_path / env.split("=")[0] / str(len(env)), spec, env)
        assert m.main() == 1, env
        out = capsys.readouterr().out
        assert "'foo_db-x'" in out or "'foo_db.x'" in out, (env, out)


def test_an_interpolated_name_is_skipped_never_read_as_a_prefix(tmp_path, monkeypatch):
    """Widening the capture must not turn `${VAR}` or `foo_${ENV}` into a false drift."""
    spec = "id: foo\nshape:\n  needs_database: true\ndepends:\n  postgres: foo_db\n"
    for env in (
        "PG_DATABASE=${PG_DATABASE}\n",
        "PG_DATABASE=foo_${ENV}\n",
        "DATABASE_URL=postgresql://u:p@h:5432/${DB_NAME}\n",
    ):
        m = _wire(monkeypatch, tmp_path / str(abs(hash(env))), spec, env)
        assert m.main() == 0, env


def test_every_dotenv_value_shape_reads_the_whole_name():
    """Review round 1 (A-O1..A-O6, A-S1, A-S2, A-H1, A-H2): the value is read the way dotenv reads
    it, so neither a prefix nor an interpolated source can stand in for the real name."""
    m = _load()
    cases = {
        # an interpolated source falls through to the next one, never stops the search
        "PG_DATABASE=${X}\nDATABASE_URL=postgresql://u:p@h:5432/foo_db\n": "foo_db",
        "PG_DATABASE=${X}\nPOSTGRES_DB=foo_db\n": "foo_db",
        "POSTGRES_DB=foo_db\nPG_DATABASE=${X}\n": "foo_db",
        # a quoted value runs to its own quote; `#`, a space or the other quote stays inside it
        'PG_DATABASE="foo#1"\n': "foo#1",
        'PG_DATABASE="foo db"\n': "foo db",
        'PG_DATABASE="foo\'x"\n': "foo'x",
        # an unquoted comment needs whitespace before its `#`
        "PG_DATABASE=foo#x\n": "foo#x",
        "PG_DATABASE=foo_db  # the app database\n": "foo_db",
        "export PG_DATABASE=foo_db\n": "foo_db",
        # the URL's host is found by a hand split, and the name is percent-decoded
        "DATABASE_URL=postgresql://u:p@h:5432/foo_db?application_name=a@b\n": "foo_db",
        "DATABASE_URL=postgresql://u:p@h:5432/my%2Ddb\n": "my-db",
        "DATABASE_URL=postgresql://${USER}:p@h:5432/foo_db\n": "foo_db",
        # review round 2 (A-O7..A-O11): a raw `/`, `#`, `?` in the password, an `@` in the query,
        # a scheme-less DSN, a non-postgres scheme, an unterminated or escaped quote
        "DATABASE_URL=postgresql://u:p/ss@h:5432/foo_db\n": "foo_db",
        "DATABASE_URL=postgresql://u:p#ss@h:5432/foo_db\n": "foo_db",
        "DATABASE_URL=postgresql://u:p?ss@h:5432/foo_db\n": "foo_db",
        "DATABASE_URL=postgresql://u:p@h:5432/foo_db?x=a@b/zz\n": "foo_db",
        "DATABASE_URL=u:p@h:5432/foo_db\n": "foo_db",
        "DATABASE_URL=sqlite:///./app.db\n": None,
        "DATABASE_URL=./data/@x/y.db\n": None,
        'PG_DATABASE="foo_db\n': None,
        'PG_DATABASE="foo\\"bar"\n': 'foo"bar',
    }
    import tempfile

    for env, want in cases.items():
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".env.example").write_text(env)
            assert m._project_db_name(Path(d)) == want, env
