"""Behavior Contract for Phase D — check_doc_stubs.py (advisory force-fill).

WARN when a seeded doc still carries template placeholders AFTER its Doc-Sync trigger fired.
Advisory only: always exits 0; fail-safe on any error.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import sys
from pathlib import Path

import pytest

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


# ── the second signal: a doc left as its scaffold template (D-593's rule, read from the hub) ──

TEMPLATE_LINE = "of its scaffold template is still verbatim in it"
SKIP_LINE = "doc-stub: template rule skipped"


@pytest.fixture(autouse=True)
def _fresh_template_audit():
    """Each test resolves the hub afresh — the loader caches the module it found."""
    stubs._template_audit.cache_clear()
    yield
    stubs._template_audit.cache_clear()


def _fixture_hub(root: Path, audit_source: str | None = None) -> Path:
    """A hub-shaped tree: the real scaffold doc templates, the registry and fleet_doc_audit.py
    (or ``audit_source`` in its place). Not a git repo, so only the current templates count."""
    shutil.copytree(
        REPO_ROOT / "templates" / "scaffold" / "docs", root / "templates" / "scaffold" / "docs"
    )
    (root / "scripts" / "enforcement").mkdir(parents=True)
    shutil.copy(ENFORCE / "_doc_registry.py", root / "scripts" / "enforcement" / "_doc_registry.py")
    target = root / "scripts" / "fleet_doc_audit.py"
    if audit_source is None:
        shutil.copy(REPO_ROOT / "scripts" / "fleet_doc_audit.py", target)
    else:
        target.write_text(audit_source)
    return root


def _proj(tmp_path: Path) -> Path:
    """The project the check runs in — a sibling of the fixture hub, never inside it."""
    proj = tmp_path / "proj"
    proj.mkdir(exist_ok=True)
    return proj


def _services_template() -> str:
    """SERVICES_TEMPLATE.md as a scaffold seeds it: the project name substituted, nothing filled."""
    raw = (REPO_ROOT / "templates" / "scaffold" / "docs" / "SERVICES_TEMPLATE.md").read_text()
    return raw.replace("[Project Name]", "acme-shop")


def test_a_doc_left_as_its_template_warns(monkeypatch, tmp_path, capsys):
    """The seeded-unfilled state the placeholder tokens miss: the real loader, a fixture hub."""
    hub = _fixture_hub(tmp_path / "hub")
    monkeypatch.setattr(stubs, "_HUB_ROOTS", (hub,))
    body = _services_template()
    assert not any(ph in body for ph in stubs.PLACEHOLDERS)  # the case the old rule could not see
    rc = _run_doc(monkeypatch, _proj(tmp_path), ["compose.yaml"], "docs/SERVICES.md", body)
    out = capsys.readouterr().out
    assert rc == 0
    assert "docs/SERVICES.md" in out and TEMPLATE_LINE in out
    assert re.search(r"\b100% of its scaffold template .*\(\d+% of the doc\)", out), out
    assert SKIP_LINE not in out


def test_a_filled_doc_keeping_template_lines_does_not_warn(monkeypatch, tmp_path, capsys):
    hub = _fixture_hub(tmp_path / "hub")
    monkeypatch.setattr(stubs, "_HUB_ROOTS", (hub,))
    kept = [ln for ln in _services_template().splitlines() if len(ln.strip()) > 25][:3]
    own = [
        f"- service-{i}: runs the acme worker pool number {i} on vps1 behind traefik"
        for i in range(40)
    ]
    rc = _run_doc(
        monkeypatch,
        _proj(tmp_path),
        ["compose.yaml"],
        "docs/SERVICES.md",
        "\n".join(["# Acme", *kept, *own]),
    )
    out = capsys.readouterr().out
    assert rc == 0 and "SERVICES.md" not in out and SKIP_LINE not in out


def test_a_template_left_doc_without_its_trigger_is_silent(monkeypatch, tmp_path, capsys):
    hub = _fixture_hub(tmp_path / "hub")
    monkeypatch.setattr(stubs, "_HUB_ROOTS", (hub,))
    rc = _run_doc(
        monkeypatch, _proj(tmp_path), ["src/app/foo.py"], "docs/SERVICES.md", _services_template()
    )
    assert rc == 0 and capsys.readouterr().out == ""


def test_without_a_hub_the_skip_is_said(monkeypatch, tmp_path, capsys):
    """Off the box: placeholders still count, and the missing second signal is said, not hidden.
    compose.yaml fires both SERVICES (a placeholder) and OPERATIONS (seeded, so only the template
    rule could see it) — the skip is owed only for a doc the placeholder rule cannot judge."""
    monkeypatch.setattr(stubs, "_HUB_ROOTS", (tmp_path / "no-hub",))
    proj = _proj(tmp_path)
    (proj / "docs").mkdir()
    (proj / "docs" / "OPERATIONS.md").write_text("# acme-shop operations\n\nseeded, never filled\n")
    rc = _run_doc(
        monkeypatch, proj, ["compose.yaml"], "docs/SERVICES.md", "# [Project Name] Services\n"
    )
    out = capsys.readouterr().out
    assert rc == 0 and "docs/SERVICES.md" in out and "placeholders" in out
    assert SKIP_LINE in out and "no hub" in out and "OPERATIONS" not in out


def test_a_placeholder_doc_alone_owes_no_skip_line(monkeypatch, tmp_path, capsys):
    """The placeholder rule already judged the only fired doc, so the hub is never consulted."""
    monkeypatch.setattr(stubs, "_HUB_ROOTS", (tmp_path / "no-hub",))
    rc = _run_doc(
        monkeypatch,
        _proj(tmp_path),
        ["compose.yaml"],
        "docs/SERVICES.md",
        "# [Project Name] Services\n",
    )
    out = capsys.readouterr().out
    assert rc == 0 and "placeholders" in out and SKIP_LINE not in out


def test_a_failing_template_audit_fails_open_loudly(monkeypatch, tmp_path, capsys):
    """A SystemExit at load (a future top-level argparse) must not turn the warn_only exit non-zero."""
    hub = _fixture_hub(tmp_path / "hub", audit_source="raise SystemExit(2)\n")
    monkeypatch.setattr(stubs, "_HUB_ROOTS", (hub,))
    rc = _run_doc(
        monkeypatch, _proj(tmp_path), ["compose.yaml"], "docs/SERVICES.md", _services_template()
    )
    out = capsys.readouterr().out
    assert rc == 0 and TEMPLATE_LINE not in out
    assert SKIP_LINE in out and "SystemExit" in out


def test_the_first_complete_hub_root_is_read(tmp_path, monkeypatch):
    """A project tree (templates without the audit, or the reverse) is skipped; the next complete root is read."""
    only_templates = tmp_path / "a"
    (only_templates / "templates" / "scaffold").mkdir(parents=True)
    only_audit = tmp_path / "b"
    (only_audit / "scripts").mkdir(parents=True)
    shutil.copy(
        REPO_ROOT / "scripts" / "fleet_doc_audit.py", only_audit / "scripts" / "fleet_doc_audit.py"
    )
    hub = _fixture_hub(tmp_path / "hub")
    monkeypatch.setattr(stubs, "_HUB_ROOTS", (only_templates, only_audit, hub))
    audit, reason = stubs._template_audit()
    assert reason is None
    assert Path(audit.__file__) == hub / "scripts" / "fleet_doc_audit.py"
    assert hub == audit.FABRIK_ROOT
