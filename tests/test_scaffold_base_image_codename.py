"""The scaffold's Debian base-image variant comes from the version registry (W-3860ebf6, D-664).

Until 2026-10-08 every scaffold type except docusaurus wrote a hard-coded ``bookworm``, while the registry
(`.windsurf/rules/versions.yaml`, key ``debian_codename``) pinned ``trixie`` and the hub's audit graded
bookworm ``superseded``. These tests point the registry at a SENTINEL codename, so a template that still
names a real codename literally fails here even after the registry and the literal happen to agree.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from fabrik import scaffold, version_registry
from fabrik.spec_loader import load_spec
from fabrik.template_renderer import TemplateRenderer

REPO_ROOT = Path(__file__).resolve().parents[1]
SENTINEL = "codenamesentinel"
TOKEN = "{{ versions.debian_codename }}"
# Real Debian release names, buster through the next two.
CODENAMES = re.compile(r"\b(buster|bullseye|bookworm|trixie|forky|duke)\b", re.I)
# A FROM line that pulls an image we build on (official python, node, debian, nginx), optional --platform.
DEBIAN_FROM = re.compile(r"^FROM\s+(--platform=\S+\s+)?(python|node|debian|nginx):", re.I)
# The Dockerfiles each type writes into its own tree (the reference copy under templates/ is checked apart).
EXPECTED = {
    "python-api": {"Dockerfile"},
    "python-api-gpu": {"Dockerfile"},
    "file-worker": {"Dockerfile"},
    "chrome-extension": {"Dockerfile"},
    "mobile-app": {"Dockerfile"},
    "node-api": {"Dockerfile"},
    "file-api": {"Dockerfile"},
    "docusaurus": {"Dockerfile"},
    "saas-skeleton": {"Dockerfile", "server/Dockerfile"},
    "static-site": {"Dockerfile", "server/Dockerfile"},
    "office-extension": {"Dockerfile", "server/Dockerfile"},
    "desktop-app": set(),
}
REFERENCE_DOCKERFILE = "templates/saas-skeleton/Dockerfile"


def _sentinel_registry(tmp: Path) -> Path:
    real = yaml.safe_load(
        (REPO_ROOT / ".windsurf" / "rules" / "versions.yaml").read_text(encoding="utf-8")
    )
    real["versions"]["debian_codename"] = SENTINEL
    path = tmp / "versions.yaml"
    path.write_text(yaml.safe_dump(real), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def scaffolded(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Every scaffoldable type, scaffolded once with the sentinel registry."""
    tmp = tmp_path_factory.mktemp("codename")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(version_registry, "VERSIONS_FILE", _sentinel_registry(tmp))
        for project_type in sorted(scaffold.SCAFFOLD_TYPES - {"wordpress"}):
            scaffold.create_project(
                name=f"p-{project_type}",
                project_type=project_type,
                description="codename probe",
                base=tmp,
                generate_spec=False,
            )
    return tmp


def _debian_froms(path: Path) -> list[str]:
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if DEBIAN_FROM.match(ln.strip())
    ]


def test_expected_covers_every_scaffoldable_type() -> None:
    assert set(EXPECTED) == scaffold.SCAFFOLD_TYPES - {"wordpress"}


@pytest.mark.parametrize("project_type", sorted(EXPECTED))
def test_every_type_emits_the_registry_codename(scaffolded: Path, project_type: str) -> None:
    project = scaffolded / f"p-{project_type}"
    found = {
        p.relative_to(project).as_posix()
        for p in project.rglob("Dockerfile")
        if p.relative_to(project).parts[0] not in ("templates", "node_modules")
    }
    assert found == EXPECTED[project_type], found
    for rel in [*sorted(found), REFERENCE_DOCKERFILE]:
        froms = _debian_froms(project / rel)
        assert froms, f"{project_type}/{rel} has no Debian-based FROM line"
        assert all(SENTINEL in ln for ln in froms), (project_type, rel, froms)


def test_no_token_survives_in_a_scaffolded_project(scaffolded: Path) -> None:
    for path in scaffolded.rglob("*"):
        if not path.is_file() or "node_modules" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        assert TOKEN not in text, path.relative_to(scaffolded)


def test_repair_recreates_dockerfile_with_registry_codename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(version_registry, "VERSIONS_FILE", _sentinel_registry(tmp_path))
    project = scaffold.create_project(
        name="p-repair",
        project_type="python-api",
        description="repair probe",
        base=tmp_path,
        generate_spec=False,
    )
    (project / "Dockerfile").unlink()
    assert "Dockerfile" in scaffold.fix_project(project, project_type="python-api")
    text = (project / "Dockerfile").read_text(encoding="utf-8")
    froms = _debian_froms(project / "Dockerfile")
    assert froms and all(SENTINEL in ln for ln in froms), froms
    # The repair loop also lacked the package-name substitutions the scaffold applies.
    assert "<package_name>" not in text and "PROJECT_NAME" not in text
    assert "p_repair.main:app" in text


def test_repair_keeps_the_doc_stub_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The package-name substitutions are the Dockerfile's: a repaired shared doc keeps `{PROJECT_NAME}`,
    the deliberate stub marker check_doc_stubs reads, exactly as a fresh scaffold writes it."""
    monkeypatch.setattr(version_registry, "VERSIONS_FILE", _sentinel_registry(tmp_path))
    project = scaffold.create_project(
        name="p-docrepair",
        project_type="python-api",
        description="doc repair probe",
        base=tmp_path,
        generate_spec=False,
    )
    quickstart = project / "docs" / "QUICKSTART.md"
    fresh = quickstart.read_text(encoding="utf-8")
    assert "{PROJECT_NAME}" in fresh
    quickstart.unlink()
    assert "docs/QUICKSTART.md" in scaffold.fix_project(project, project_type="python-api")
    assert "{PROJECT_NAME}" in quickstart.read_text(encoding="utf-8")


def test_repair_fills_the_package_name_in_docs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`<package_name>` is a fill-in, not a stub: a repaired TROUBLESHOOTING.md names the package as a
    fresh scaffold does."""
    monkeypatch.setattr(version_registry, "VERSIONS_FILE", _sentinel_registry(tmp_path))
    project = scaffold.create_project(
        name="p-pkgrepair",
        project_type="python-api",
        description="package repair probe",
        base=tmp_path,
        generate_spec=False,
    )
    doc = project / "docs" / "TROUBLESHOOTING.md"
    fresh = doc.read_text(encoding="utf-8")
    assert "<package_name>" not in fresh and "p_pkgrepair" in fresh
    doc.unlink()
    assert "docs/TROUBLESHOOTING.md" in scaffold.fix_project(project, project_type="python-api")
    assert "<package_name>" not in doc.read_text(encoding="utf-8")


@pytest.mark.parametrize("template", ["file-worker", "file-api", "node-api"])
def test_renderer_dockerfiles_use_the_registry_codename(
    template: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(version_registry, "VERSIONS_FILE", _sentinel_registry(tmp_path))
    spec_path = tmp_path / "probe.yaml"
    spec_path.write_text(
        yaml.safe_dump(
            {
                "id": "codename-probe",
                "kind": "service",
                "template": template,
                "domain": "codename-probe.vps1.ocoron.com",
                "source": {"type": "template"},
                "resources": {"memory": "256M", "cpu": "0.5"},
            }
        )
    )
    rendered = TemplateRenderer(output_dir=tmp_path / "out").render(
        load_spec(spec_path), dry_run=True
    )
    froms = [ln for ln in rendered["Dockerfile"].splitlines() if DEBIAN_FROM.match(ln)]
    assert froms and all(SENTINEL in ln for ln in froms), froms


@pytest.mark.parametrize("project_type", ["python-api", "node-api"])
def test_missing_registry_fails_before_writing(
    project_type: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(version_registry, "VERSIONS_FILE", tmp_path / "absent.yaml")
    with pytest.raises(version_registry.VersionRegistryError):
        scaffold.create_project(
            name="p-noregistry",
            project_type=project_type,
            description="registry probe",
            base=tmp_path,
            generate_spec=False,
        )
    assert not (tmp_path / "p-noregistry").exists()


def _template_files() -> list[Path]:
    globs = [
        "templates/**/Dockerfile*",
        "templates/**/compose*.j2",
        "templates/scaffold/docs/*.md",
        "templates/spec-pipeline/*.md",
    ]
    files = {p for g in globs for p in REPO_ROOT.glob(g) if p.is_file()}
    return sorted([*files, REPO_ROOT / "src" / "fabrik" / "scaffold.py"])


def test_no_template_names_a_codename_literally() -> None:
    hits = []
    for path in _template_files():
        builds = path.name.startswith(("Dockerfile", "compose")) or path.suffix == ".py"
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not CODENAMES.search(line):
                continue
            # Any mention in a build file (a comment naming the variant goes stale too), or a
            # base-image mention in prose.
            if builds or "slim" in line or "base image" in line.lower():
                hits.append(f"{path.relative_to(REPO_ROOT)}:{n}: {line.strip()}")
    assert not hits, hits
