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


def test_an_unusable_value_on_any_key_is_named_not_dropped(tmp_path: Path) -> None:
    # A non-required key holding a float would otherwise vanish and render empty in a template
    # that reads it (closing pass N2); a null or blank one is simply absent.
    with pytest.raises(VersionRegistryError, match="meilisearch_major"):
        load_versions(_registry(tmp_path, {**GOOD, "meilisearch_major": 1.10}))
    got = load_versions(_registry(tmp_path, {**GOOD, "unset": None, "blank": " "}))
    assert "unset" not in got and "blank" not in got


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
    with pytest.raises(VersionRegistryError, match=r"not found: .*nope\.yaml"):
        load_versions(missing)


def test_an_unrelated_error_is_not_relabelled_as_a_registry_error() -> None:
    # A narrow catch: a caller bug (a non-Path source) must surface as itself, never as
    # "version registry unreadable" (the scoped review's escape variant S2).
    with pytest.raises(AttributeError):
        load_versions(42)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [["node_lts"], "24", None])
def test_a_non_mapping_versions_block_is_named(tmp_path: Path, bad: object) -> None:
    path = _registry(tmp_path, bad)
    with pytest.raises(VersionRegistryError, match="versions.yaml"):
        load_versions(path)


def test_an_unparseable_registry_is_named(tmp_path: Path) -> None:
    path = tmp_path / "versions.yaml"
    path.write_text("versions: [unclosed\n")
    with pytest.raises(VersionRegistryError, match=r"unreadable: .*versions\.yaml"):
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
    (nested_templates / "t" / "Dockerfile.j2").write_text("FROM top\n")
    (nested_templates / "t" / "a" / "compose.yaml.j2").write_text("nested {{ name }}\n")
    (nested_templates / "t" / "a" / "Dockerfile.j2").write_text("FROM nested\n")
    rendered = TemplateRenderer(templates_dir=nested_templates, output_dir=tmp_path / "out").render(
        _spec(tmp_path, "t"), dry_run=True
    )
    assert rendered["a/compose.yaml"].strip() == "nested nested-probe"
    assert rendered["a/Dockerfile"].strip() == "FROM nested"
    assert rendered["compose.yaml"].strip() == "services: {}"
    assert rendered["Dockerfile"].strip() == "FROM top"


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


# ── Phase B: the docusaurus templates through both emitters ─────────────────

NESTED = ("src/pages/index.js", "src/theme/SearchBar/index.js")
PARITY = ("Dockerfile", "nginx.conf", *NESTED)
INSTALL = (
    "RUN if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; "
    "else npm install --no-audit --no-fund; fi"
)


@pytest.fixture(scope="module")
def scaffolded(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from fabrik.scaffold import create_project

    base = tmp_path_factory.mktemp("scaffold")
    return create_project(
        name="docs-probe",
        description="Docs probe",
        base=base,
        project_type="docusaurus",
        generate_spec=False,
    )


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    tmp = tmp_path_factory.mktemp("render")
    return TemplateRenderer(output_dir=tmp / "out").render(
        _spec(tmp, "docusaurus", spec_id="docs-probe"), dry_run=True
    )


def _dockerfile_rows(text: str) -> None:
    v = load_versions()
    froms = [ln for ln in text.splitlines() if ln.startswith("FROM ")]
    assert froms == [
        f"FROM node:{v['node_lts']}-{v['debian_codename']}-slim AS builder",
        f"FROM nginx:mainline-{v['debian_codename']}",
    ], froms
    assert "RUN npm run build && npx -y pagefind --site build" in text
    assert "COPY package*.json ./" in text
    runs = [
        ln for ln in text.splitlines() if ln.startswith("RUN") and "npm" in ln and "build" not in ln
    ]
    assert runs == [INSTALL], runs
    assert "npm run serve" not in text and "docusaurus serve" not in text
    assert 'CMD ["npm"' not in text and "CMD npm" not in text
    assert "EXPOSE 80" in text and "http://localhost:80/docs/intro/" in text


def _nginx_rows(text: str) -> None:
    assert "try_files $uri $uri/ /index.html;" in text
    assert "absolute_redirect off;" in text
    assert "gzip on;" in text
    gzip_types = next(ln for ln in text.splitlines() if "gzip_types" in ln).split()
    assert set(gzip_types[1:]) == {
        "text/css",
        "application/javascript",
        "application/json",
        "image/svg+xml",
        "application/wasm;",
    }
    assets = text[text.index("location /assets/") : text.index("location / {")]
    assert 'add_header Cache-Control "public, max-age=31536000, immutable";' in assets
    assert text.count("immutable") == 1, "the immutable header must live in /assets/ only"


def _nested_rows(files: dict[str, str]) -> None:
    for rel in NESTED:
        assert "{%" not in files[rel] and "{{" not in files[rel] and "endraw" not in files[rel], rel
    assert '<Redirect to="/docs/intro" />' in files["src/pages/index.js"]
    bar = files["src/theme/SearchBar/index.js"]
    assert "<pagefind-modal-trigger></pagefind-modal-trigger>" in bar
    assert "<pagefind-modal></pagefind-modal>" in bar
    head = bar[bar.index("<Head>") : bar.index("</Head>")]
    assert '<script type="module" src="/pagefind/pagefind-component-ui.js"></script>' in head
    assert '<link rel="stylesheet" href="/pagefind/pagefind-component-ui.css" />' in head


def _package_rows(text: str, name: str) -> None:
    import json

    pkg = json.loads(text)
    assert pkg["devDependencies"]["pagefind"] == "^1.5.2"
    assert "serve" not in pkg["scripts"]
    assert pkg["engines"]["node"] == f">={load_versions()['node_engines_floor']}"
    assert pkg["name"] == f"{name}-docs"


def _scaffold_files(root: Path) -> dict[str, str]:
    return {
        rel: (root / rel).read_text()
        for rel in (*PARITY, "package.json", "compose.yaml", ".env.example")
    }


def test_scaffold_dockerfile_is_the_static_two_stage_build(scaffolded: Path) -> None:
    _dockerfile_rows((scaffolded / "Dockerfile").read_text())


def test_scaffold_nginx_conf_follows_the_pack(scaffolded: Path) -> None:
    _nginx_rows((scaffolded / "nginx.conf").read_text())


def test_scaffold_compose_serves_port_80_with_no_middleware(scaffolded: Path) -> None:
    compose = yaml.safe_load((scaffolded / "compose.yaml").read_text())
    (svc,) = compose["services"].values()
    labels = svc["labels"]
    assert any(lb.endswith("loadbalancer.server.port=80") for lb in labels), labels
    assert not any("middlewares" in lb for lb in labels), labels
    assert svc["healthcheck"]["test"] == ["CMD", "curl", "-f", "http://localhost:80/docs/intro/"]
    assert set(svc["environment"]) == {"PORT=80", "LOG_LEVEL=INFO"}, svc["environment"]
    assert "NODE_ENV" not in (scaffolded / ".env.example").read_text()


def test_scaffold_writes_the_root_page_and_the_search_bar(scaffolded: Path) -> None:
    _nested_rows({rel: (scaffolded / rel).read_text() for rel in NESTED})


def test_scaffold_package_json_has_pagefind_and_registry_engines(scaffolded: Path) -> None:
    _package_rows((scaffolded / "package.json").read_text(), "docs-probe")


def test_renderer_emits_the_same_docusaurus_shape(rendered: dict[str, str]) -> None:
    _dockerfile_rows(rendered["Dockerfile"])
    _nginx_rows(rendered["nginx.conf"])
    _nested_rows(rendered)
    _package_rows(rendered["package.json"], "docs-probe")
    compose = yaml.safe_load(rendered["compose.yaml"])
    (svc,) = compose["services"].values()
    assert "environment" not in svc, svc.get("environment")
    assert any(lb.endswith("loadbalancer.server.port=80") for lb in svc["labels"])
    assert not any("middlewares" in lb for lb in svc["labels"])
    assert svc["healthcheck"]["test"] == ["CMD", "curl", "-f", "http://localhost:80/docs/intro/"]


def test_both_emitters_write_the_same_files(scaffolded: Path, rendered: dict[str, str]) -> None:
    for rel in PARITY:
        assert (scaffolded / rel).read_text().rstrip("\n") == rendered[rel].rstrip("\n"), rel


def test_scaffold_fails_by_key_name_on_a_broken_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fabrik.scaffold import create_project

    versions = {k: v for k, v in GOOD.items() if k != "debian_codename"}
    monkeypatch.setattr(version_registry, "VERSIONS_FILE", _registry(tmp_path, versions))
    with pytest.raises(VersionRegistryError, match="debian_codename"):
        create_project(
            name="docs-broken",
            description="x",
            base=tmp_path,
            project_type="docusaurus",
            generate_spec=False,
        )


def test_spec_generator_health_path_is_the_slashed_intro() -> None:
    from fabrik.spec_generator import generate_spec

    spec = generate_spec("my-docs", "docusaurus", "my-docs.vps1.ocoron.com")
    assert spec.health.path == "/docs/intro/"


def test_scaffold_dockerignore_keeps_the_docs_in_the_build_context(scaffolded: Path) -> None:
    # The generic .dockerignore drops `docs/` and `*.md` — a docusaurus site's content — and the
    # builder then fails with "The docs folder does not exist" (Phase B review O2, reproduced by a
    # real docker build). Secrets, node_modules and build output stay out.
    rules = {
        ln.strip()
        for ln in (scaffolded / ".dockerignore").read_text().splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    }
    assert not rules & {"docs/", "docs", "*.md", "src/", "static/"}, rules
    assert {".env", "node_modules/", "build/", ".docusaurus/", ".git/"} <= rules, rules
