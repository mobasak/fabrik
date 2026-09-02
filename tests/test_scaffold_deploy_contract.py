"""Phase C of docs/development/plans/2026-09-01-plan-1-deployment-verification.md — born compliant.

Every SCAFFOLDABLE type seeds the deployment-verification contract stub (exits 2 until authored),
the vendored health-probe it imports, and the fleet-AI doc sections; `wordpress` is refused, not
seeded; a `docusaurus` scaffold publishes none of the new doc sections (they are deployed-docs,
which that type never receives). Scaffolds are cached per type — every test here only READS.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from fabrik.scaffold import SCAFFOLD_TYPES, create_project

REPO = Path(__file__).resolve().parents[1]
_HUB_VENDORED = REPO / "libs" / "health_probe"
_LIB_SRC = Path("/opt/fabrik-lib/health-probe")
SCAFFOLDABLE = sorted(t for t in SCAFFOLD_TYPES if t != "wordpress")

_CACHE: dict[str, Path] = {}


def _scaffold(tmp_path_factory: pytest.TempPathFactory, project_type: str) -> Path:
    cached = _CACHE.get(project_type)
    if cached is not None and cached.exists():
        return cached
    base = tmp_path_factory.mktemp(f"dc-{project_type}")
    name = f"dc-{project_type}"
    create_project(
        name=name,
        project_type=project_type,
        description="deploy-contract test",
        base=base,
        generate_spec=False,
    )
    out = base / name
    _CACHE[project_type] = out
    return out


def _run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(cwd)}
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_denominator_is_the_live_registry_minus_wordpress():
    assert len(SCAFFOLDABLE) == len(SCAFFOLD_TYPES) - 1, SCAFFOLD_TYPES


@pytest.mark.parametrize("project_type", SCAFFOLDABLE)
def test_stub_seeded_and_exits_2(tmp_path_factory, project_type):
    p = _scaffold(tmp_path_factory, project_type)
    stub = p / "scripts" / "verify_prod_parity.py"
    assert stub.is_file(), f"{project_type}: stub not seeded"
    assert os.access(stub, os.X_OK), f"{project_type}: stub not executable"
    hdr = json.loads(_run(stub, "--header", cwd=p).stdout)
    assert hdr["parsed"] == "true" and hdr["status"] == "DRAFT" and hdr["version"] == "v0"
    r = _run(stub, "--json", cwd=p)
    assert r.returncode == 2, (
        f"{project_type}: an unfilled contract must fail closed (exit 2), got {r.returncode}: {r.stderr}"
    )
    rows = json.loads(r.stdout)
    assert rows and rows[0]["system"] == "l0_health_probe_vendored" and rows[0]["match"] is True, (
        rows
    )


@pytest.mark.parametrize("project_type", SCAFFOLDABLE)
def test_health_probe_vendored_and_in_sync(tmp_path_factory, project_type):
    p = _scaffold(tmp_path_factory, project_type)
    for name in ("health_probe.py", "fingerprint.py", "__init__.py"):
        seeded = p / "libs" / "health_probe" / name
        assert seeded.is_file(), f"{project_type}: {name} not seeded"
        assert seeded.read_bytes() == (_HUB_VENDORED / name).read_bytes(), (
            f"{project_type}: {name} differs from the hub's copy"
        )


@pytest.mark.skipif(not _LIB_SRC.is_dir(), reason="fabrik-lib not present on this box")
def test_hub_copy_differs_from_fabrik_lib_only_by_the_vendoring_header():
    for name in ("health_probe.py", "fingerprint.py"):
        hub = (_HUB_VENDORED / name).read_text(encoding="utf-8").splitlines(keepends=True)
        lib = (_LIB_SRC / name).read_text(encoding="utf-8").splitlines(keepends=True)
        assert hub[0].startswith(f"# VENDORED-FROM fabrik-lib health-probe/{name} @ "), hub[0]
        assert hub[1] == "# ruff: noqa\n" and hub[2] == "# fmt: off\n"
        assert hub[3:] == lib, f"{name}: drift below the header — re-vendor, never edit"


def test_vendored_dir_is_in_the_synced_manifest():
    sys.path.insert(0, str(REPO / "scripts"))
    from fabrik_synced_manifest import VENDORED_DIRS  # noqa: PLC0415

    assert "libs/health_probe" in VENDORED_DIRS


def test_stub_without_vendored_module_fails_closed(tmp_path):
    """The lazy import: no libs/health_probe on the path → the precondition row is UNVERIFIABLE,
    exit 2, no traceback."""
    stub = REPO / "templates" / "scaffold" / "scripts" / "verify_prod_parity.py"
    bare = tmp_path / "bare"
    bare.mkdir()
    r = _run(stub, "--json", cwd=bare)
    assert r.returncode == 2 and "Traceback" not in r.stderr, r.stderr
    rows = json.loads(r.stdout)
    assert rows[0]["match"] is None and rows[0]["detail"].startswith(
        "UNVERIFIABLE (health_probe not vendored"
    )


def test_wordpress_is_not_scaffolded(tmp_path):
    with pytest.raises(NotImplementedError):
        create_project(
            name="dc-wp",
            project_type="wordpress",
            description="x",
            base=tmp_path,
            generate_spec=False,
        )
    assert not (tmp_path / "dc-wp").exists()


def test_fleet_ai_sections_present_in_the_templates():
    dep = (REPO / "templates/scaffold/docs/DEPLOYMENT_TEMPLATE.md").read_text()
    ops = (REPO / "templates/scaffold/docs/OPERATIONS_TEMPLATE.md").read_text()
    assert (
        "## Fleet-AI interface — what to deploy" in dep
        and "{PROJECT_NAME}: to be filled by /fabrik-deploy-checklist" in dep
    )
    assert (
        "## 5b. Fleet-AI interface — what runs" in ops
        and "{PROJECT_NAME}: to be filled by /fabrik-deploy-checklist" in ops
    )
    # the sentinel is one check_doc_stubs recognises (its PLACEHOLDERS tuple), so an unfilled stub is visible
    sys.path.insert(0, str(REPO / "scripts" / "enforcement"))
    from check_doc_stubs import PLACEHOLDERS  # noqa: PLC0415

    assert "{PROJECT_NAME}" in PLACEHOLDERS


def test_docusaurus_does_not_publish_fleet_ai_sections(tmp_path_factory):
    """docusaurus publishes its whole docs/ tree; the deployed-docs bucket (DEPLOYMENT/OPERATIONS)
    is never seeded there — so the new sections cannot leak. Assert the absence, not a config."""
    p = _scaffold(tmp_path_factory, "docusaurus")
    assert not (p / "docs" / "DEPLOYMENT.md").exists()
    assert not (p / "docs" / "OPERATIONS.md").exists()
    assert not list(p.rglob("*Fleet-AI interface*"))
