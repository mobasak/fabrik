"""Behavior Contract for Phase D — check_doc_stubs.py (advisory force-fill).

WARN when a seeded doc still carries template placeholders AFTER its Doc-Sync trigger fired.
Advisory only: always exits 0; fail-safe on any error.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENFORCE = REPO_ROOT / "scripts" / "enforcement"


def _load(mod_name: str):
    if str(ENFORCE) not in sys.path:
        sys.path.insert(0, str(ENFORCE))
    spec = importlib.util.spec_from_file_location(mod_name, ENFORCE / f"{mod_name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


stubs = _load("check_doc_stubs")
ds = _load("check_doc_sync")


def test_has_placeholder_detects_every_sentinel_and_clears(tmp_path: Path):
    stub = tmp_path / "d.md"
    # every sentinel in PLACEHOLDERS must be detected (guards a dropped/mistyped entry)
    for ph in stubs.PLACEHOLDERS:
        stub.write_text(f"# heading\n\ncontains {ph} here\n")
        assert stubs._has_placeholder(stub), f"{ph!r} not detected"
    stub.write_text("# Acme API\n\nShipped 2026-07-11, fully filled.\n")
    assert not stubs._has_placeholder(stub)
    assert not stubs._has_placeholder(tmp_path / "missing.md")  # absent → False, no raise


def _run(monkeypatch, tmp_path: Path, staged, service_body: str | None):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ds, "_staged", lambda: staged)
    if service_body is not None:
        (tmp_path / "docs").mkdir(exist_ok=True)
        (tmp_path / "docs" / "SERVICES.md").write_text(service_body)
    return stubs.main()


def test_warns_when_trigger_fired_and_stub(monkeypatch, tmp_path, capsys):
    # compose.yaml staged (SERVICES trigger) + a placeholder-bearing docs/SERVICES.md → WARN
    rc = _run(monkeypatch, tmp_path, ["compose.yaml"], "# [Project Name] Services\n")
    out = capsys.readouterr().out
    assert rc == 0
    assert "docs/SERVICES.md" in out and "placeholders" in out


def test_no_warn_when_doc_is_filled(monkeypatch, tmp_path, capsys):
    rc = _run(monkeypatch, tmp_path, ["compose.yaml"], "# Acme Services\n\nReal content.\n")
    out = capsys.readouterr().out
    assert rc == 0
    assert "SERVICES.md" not in out


def test_no_warn_when_trigger_not_fired(monkeypatch, tmp_path, capsys):
    # a src change with NO compose → SERVICES trigger did not fire → no WARN even though stub
    rc = _run(monkeypatch, tmp_path, ["src/app/foo.py"], "# [Project Name] Services\n")
    out = capsys.readouterr().out
    assert rc == 0
    assert "SERVICES.md" not in out


def test_failsafe_returns_zero_on_git_error(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    def _boom():
        raise RuntimeError("git blew up")

    monkeypatch.setattr(ds, "_staged", _boom)
    assert stubs.main() == 0  # never blocks, even when git fails


def test_empty_stage_is_noop(monkeypatch, tmp_path, capsys):
    rc = _run(monkeypatch, tmp_path, [], None)
    assert rc == 0
    assert capsys.readouterr().out == ""


def _run_doc(monkeypatch, tmp_path, staged, doc_rel, body):
    """Generic runner: stage `staged`, drop a placeholder-bearing doc at doc_rel, run main()."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ds, "_staged", lambda: staged)
    p = tmp_path / doc_rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    return stubs.main()


def test_env_trigger_warns_configuration_stub(monkeypatch, tmp_path, capsys):
    rc = _run_doc(
        monkeypatch,
        tmp_path,
        [".env.example"],
        "docs/CONFIGURATION.md",
        "# [Project Name] config\n",
    )
    assert rc == 0 and "docs/CONFIGURATION.md" in capsys.readouterr().out


def test_schema_trigger_warns_data_contract_stub(monkeypatch, tmp_path, capsys):
    rc = _run_doc(
        monkeypatch,
        tmp_path,
        ["db/migrations/001_init.sql"],
        "docs/data-contract.md",
        "# [PROJECT_NAME]\n",
    )
    assert rc == 0 and "docs/data-contract.md" in capsys.readouterr().out


def test_route_trigger_warns_quickstart_stub(monkeypatch, tmp_path, capsys):
    # a staged .py with a real FastAPI route → QUICKSTART trigger (reused check_doc_sync detector)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "api.py").write_text("@app.get('/x')\ndef x(): ...\n")
    monkeypatch.setattr(ds, "_staged", lambda: ["src/api.py"])
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "QUICKSTART.md").write_text("# [Project Name] quickstart\n")
    rc = stubs.main()
    assert rc == 0 and "docs/QUICKSTART.md" in capsys.readouterr().out


def test_registry_alignment_doc_not_in_registry_is_skipped(monkeypatch, tmp_path, capsys):
    # a detector doc that is NOT in the SSOT registry must not warn (drift guard)
    import _doc_registry

    monkeypatch.setattr(_doc_registry, "PROJECT_DOCS", ())  # empty registry → nothing checked
    rc = _run_doc(monkeypatch, tmp_path, ["compose.yaml"], "docs/SERVICES.md", "# [Project Name]\n")
    assert rc == 0 and "SERVICES.md" not in capsys.readouterr().out


def test_detector_keys_are_all_registry_docs():
    # every mechanically-detected doc must be a real registry doc (drift guard — a rename in
    # the registry that isn't mirrored here shows up as a stale detector key)
    import _doc_registry

    reg_names = {r.name for r in _doc_registry.PROJECT_DOCS}
    for doc in stubs._trigger_detectors():
        assert doc in reg_names, f"detector doc {doc!r} is not in the registry SSOT"


def test_inner_detector_exception_is_swallowed(monkeypatch, tmp_path):
    # a detector raising is caught by the INNER except → exit 0, no crash (fleet never-block)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ds, "_staged", lambda: ["compose.yaml"])

    def _boom(staged):
        raise RuntimeError("detector blew up")

    monkeypatch.setattr(stubs, "_trigger_detectors", lambda: {"docs/SERVICES.md": _boom})
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SERVICES.md").write_text("# [Project Name]\n")
    assert stubs.main() == 0


def test_filled_data_contract_with_date_format_does_not_warn(monkeypatch, tmp_path, capsys):
    # regression for the native review: a FILLED data-contract that documents a DATE column's
    # YYYY-MM-DD format must NOT be flagged as an unfilled stub (dates aren't placeholders)
    rc = _run_doc(
        monkeypatch,
        tmp_path,
        ["db/migrations/001.sql"],
        "docs/data-contract.md",
        "# Acme data contract\n\n`created_at` DATE — format YYYY-MM-DD (e.g. 2026-07-11).\n",
    )
    assert rc == 0 and "data-contract.md" not in capsys.readouterr().out
