"""The docusaurus static runtime: the version registry loader and the template emitter.

Plan: docs/development/plans/2026-10-01-plan-1-docusaurus-static-runtime.md (D-475, D-476).
Phase A rows: the registry loader fails by key name, and `TemplateRenderer` renders nested `*.j2`
files with `versions` and `name` in its context.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from fabrik import version_registry
from fabrik.spec_loader import load_spec
from fabrik.template_renderer import TemplateRenderer
from fabrik.version_registry import REQUIRED_KEYS, VersionRegistryError, load_versions

GOOD = {"node_lts": "24", "debian_codename": "trixie", "node_engines_floor": "22", "other": "x"}


def _registry(tmp_path: Path, versions: object) -> Path:
    path = tmp_path / "versions.yaml"
    path.write_text(yaml.safe_dump({"updated": "2026-10-01", "versions": versions}))
    return path


@pytest.fixture
def registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = _registry(tmp_path, dict(GOOD))
    monkeypatch.setattr(version_registry, "VERSIONS_FILE", path)
    return path


def _spec(tmp_path: Path, template: str, spec_id: str = "nested-probe") -> object:
    spec_path = tmp_path / f"{spec_id}.yaml"
    spec_path.write_text(
        yaml.safe_dump(
            {
                "id": spec_id,
                "kind": "static",
                "template": template,
                "domain": f"{spec_id}.vps1.ocoron.com",
                "source": {"type": "template"},
                "resources": {"memory": "256M", "cpu": "0.5"},
            }
        )
    )
    return load_spec(spec_path)


@pytest.fixture
def nested_templates(tmp_path: Path) -> Path:
    root = tmp_path / "templates"
    (root / "t" / "a" / "b").mkdir(parents=True)
    (root / "t" / "compose.yaml.j2").write_text("services: {}\n")
    (root / "t" / "a" / "b" / "x.txt.j2").write_text("{{ versions.node_lts }}-{{ name }}\n")
    return root


# ── the loader ──────────────────────────────────────────────────────────────


def test_load_versions_returns_the_map_as_strings(registry: Path) -> None:
    got = load_versions()
    assert got["node_lts"] == "24" and got["debian_codename"] == "trixie"
    assert got["node_engines_floor"] == "22"
    assert all(isinstance(v, str) and v for v in got.values())


def test_load_versions_coerces_a_numeric_value_to_str(tmp_path: Path) -> None:
    path = _registry(tmp_path, {**GOOD, "node_lts": 24})
    assert load_versions(path)["node_lts"] == "24"


@pytest.mark.parametrize("key", REQUIRED_KEYS)
@pytest.mark.parametrize("shape", ["absent", "null", "empty"])
def test_a_missing_or_empty_required_key_is_named(tmp_path: Path, key: str, shape: str) -> None:
    versions = dict(GOOD)
    if shape == "absent":
        del versions[key]
    elif shape == "null":
        versions[key] = None
    else:
        versions[key] = "  "
    with pytest.raises(VersionRegistryError, match=key):
        load_versions(_registry(tmp_path, versions))


def test_a_missing_registry_file_is_named(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"
    with pytest.raises(VersionRegistryError, match="nope.yaml"):
        load_versions(missing)


@pytest.mark.parametrize("bad", [["node_lts"], "24", None])
def test_a_non_mapping_versions_block_is_named(tmp_path: Path, bad: object) -> None:
    path = _registry(tmp_path, bad)
    with pytest.raises(VersionRegistryError, match="versions.yaml"):
        load_versions(path)


def test_an_unparseable_registry_is_named(tmp_path: Path) -> None:
    path = tmp_path / "versions.yaml"
    path.write_text("versions: [unclosed\n")
    with pytest.raises(VersionRegistryError, match="versions.yaml"):
        load_versions(path)


def test_the_live_registry_carries_the_required_keys() -> None:
    got = load_versions()
    assert set(REQUIRED_KEYS) <= set(got)


# ── the template emitter ────────────────────────────────────────────────────


def test_renderer_fails_by_key_name_and_writes_no_spec_dir(
    tmp_path: Path, nested_templates: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    versions = {k: v for k, v in GOOD.items() if k != "node_lts"}
    monkeypatch.setattr(version_registry, "VERSIONS_FILE", _registry(tmp_path, versions))
    out = tmp_path / "out"
    renderer = TemplateRenderer(templates_dir=nested_templates, output_dir=out)
    with pytest.raises(VersionRegistryError, match="node_lts"):
        renderer.render(_spec(tmp_path, "t"))
    assert not (out / "nested-probe").exists()


def test_renderer_renders_a_nested_template_with_versions_and_name(
    tmp_path: Path, nested_templates: Path, registry: Path
) -> None:
    rendered = TemplateRenderer(templates_dir=nested_templates, output_dir=tmp_path / "out").render(
        _spec(tmp_path, "t"), dry_run=True
    )
    assert rendered["a/b/x.txt"].strip() == "24-nested-probe"


def test_renderer_writes_a_nested_template_to_disk(
    tmp_path: Path, nested_templates: Path, registry: Path
) -> None:
    out = tmp_path / "out"
    TemplateRenderer(templates_dir=nested_templates, output_dir=out).render(_spec(tmp_path, "t"))
    assert (out / "nested-probe" / "a" / "b" / "x.txt").read_text().strip() == "24-nested-probe"


def test_a_nested_file_named_like_a_top_level_one_still_renders(
    tmp_path: Path, nested_templates: Path, registry: Path
) -> None:
    (nested_templates / "t" / "a" / "compose.yaml.j2").write_text("nested {{ name }}\n")
    rendered = TemplateRenderer(templates_dir=nested_templates, output_dir=tmp_path / "out").render(
        _spec(tmp_path, "t"), dry_run=True
    )
    assert rendered["a/compose.yaml"].strip() == "nested nested-probe"
    assert rendered["compose.yaml"].strip() == "services: {}"


# ── round-1 review fixes (/fabrik-review-scoped, Phase A) ───────────────────


@pytest.mark.parametrize("key", REQUIRED_KEYS)
@pytest.mark.parametrize(
    "bad", [24.0, True, ["24"], {"v": 24}], ids=["float", "bool", "list", "dict"]
)
def test_a_required_key_of_the_wrong_type_is_named(tmp_path: Path, key: str, bad: object) -> None:
    # A float, bool, list or dict would render as `24.0`, `True`, `['24']` into an image tag.
    with pytest.raises(VersionRegistryError, match=key):
        load_versions(_registry(tmp_path, {**GOOD, key: bad}))


def test_a_non_utf8_registry_is_named(tmp_path: Path) -> None:
    path = tmp_path / "versions.yaml"
    path.write_bytes(b"versions:\n  node_lts: \xff\xfe\n")
    with pytest.raises(VersionRegistryError, match="versions.yaml"):
        load_versions(path)


def test_a_directory_named_like_a_template_is_not_rendered(
    tmp_path: Path, nested_templates: Path, registry: Path
) -> None:
    (nested_templates / "t" / "dir.j2").mkdir()
    rendered = TemplateRenderer(templates_dir=nested_templates, output_dir=tmp_path / "out").render(
        _spec(tmp_path, "t"), dry_run=True
    )
    assert "dir" not in rendered
