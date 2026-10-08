"""The docusaurus static runtime: the version registry loader and the template emitter.

Plan: docs/development/plans/archived/2026-10-01-plan-1-docusaurus-static-runtime.md (D-475, D-476).
Phase A rows: the registry loader fails by key name, and `TemplateRenderer` renders nested `*.j2`
files with `versions` and `name` in its context. Phase B rows: both emitters produce the nginx static
runtime. Phase C: one opt-in real build (`FABRIK_REAL_DOCKER_BUILD=1`).
"""

from __future__ import annotations

import os
import posixpath
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest
import yaml

from fabrik import version_registry
from fabrik.spec_loader import load_spec
from fabrik.template_renderer import TemplateRenderer
from fabrik.version_registry import REQUIRED_KEYS, VersionRegistryError, load_versions

# The tree this test file ships in: a grader of the sync manifest or check_structure.py reads
# THESE copies, never FABRIK_ROOT, which falls back to the live hub outside a hub worktree.
REPO_ROOT = Path(__file__).resolve().parents[1]

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
    # The pack (.windsurf/rules/core/42-docusaurus.md, D-664) owns the serve config; the scaffold
    # ships its fenced nginx block verbatim, so the two cannot drift apart.
    pack = (REPO_ROOT / ".windsurf" / "rules" / "core" / "42-docusaurus.md").read_text(
        encoding="utf-8"
    )
    blocks = re.findall(r"```nginx\n(.*?)```", pack, flags=re.S)
    assert len(blocks) == 1, len(blocks)
    # template_renderer's Jinja env drops the final newline; nginx does not care.
    assert text.rstrip("\n") == blocks[0].rstrip("\n")
    # The behaviours the block exists for, named so a pack edit that drops one fails here too.
    lookups = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("try_files")]
    assert lookups == ["try_files $uri $uri.html $uri/index.html =404;"], lookups
    assert "=200" not in text and "rewrite" not in text, "no SPA fallback by another spelling"
    # A 404 may only be answered by the build's 404 page: no other error_page, no `return`.
    errors = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("error_page")]
    assert errors == ["error_page 404 /404.html;"], errors
    assert "return " not in text
    assert "error_page 404 /404.html;" in text
    assert "absolute_redirect off;" in text
    assert "gzip on;" in text and "gzip_vary on;" in text
    gzip_types = next(ln for ln in text.splitlines() if "gzip_types" in ln).split()
    assert set(gzip_types[1:]) == {
        "text/css",
        "application/javascript",
        "application/json",
        "image/svg+xml",
        "application/wasm",
        "text/xml;",
    }
    page = text[text.index("location / {") : text.index("location /assets/")]
    assert 'add_header Cache-Control "no-cache";' in page
    assets = text[text.index("location /assets/") : text.index("error_page")]
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


def _ignored(rules: list[str], path: str) -> bool:
    """Whether a .dockerignore rule set excludes ``path``, read as Docker reads it: each rule is
    cleaned (`./docs` is `docs`) and anchored at the context root, `*` and `?` stay inside one
    segment, `**/` is zero or more directories, `[...]` is a character class, a rule that
    matches a parent directory excludes everything below it, a `!` rule re-includes, and the
    LAST matching rule decides."""
    parts = path.split("/")
    excluded = False
    for raw in rules:
        rule = raw.strip()
        negate = rule.startswith("!")
        body = posixpath.normpath(rule.lstrip("!").strip()).strip("/")
        tokens = re.split(r"(\*\*/|\*\*|\*|\?|\[[^\]]*\])", body)
        pattern = "".join(
            "(?:.*/)?"
            if tok == "**/"
            else ".*"
            if tok == "**"
            else "[^/]*"
            if tok == "*"
            else "[^/]"
            if tok == "?"
            else tok
            if tok.startswith("[") and tok.endswith("]")
            else re.escape(tok)
            for tok in tokens
            if tok
        )
        if any(re.fullmatch(pattern, "/".join(parts[:n])) for n in range(1, len(parts) + 1)):
            excluded = not negate
    return excluded


def test_scaffold_dockerignore_keeps_every_build_input(scaffolded: Path) -> None:
    # The generic .dockerignore drops `docs/` and `*.md` — a docusaurus site's content — and the
    # builder then fails with "The docs folder does not exist" (Phase B review O2, reproduced by a
    # real docker build). Every file the build reads is checked against every rule, so any spelling
    # of that exclusion (`/docs`, `docs/**`, `**/*.md`, `src`) fails here (closing pass C2).
    rules = [
        ln.strip()
        for ln in (scaffolded / ".dockerignore").read_text().splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    inputs = [
        f.relative_to(scaffolded).as_posix()
        for top in ("docs", "src", "static")
        for f in (scaffolded / top).rglob("*")
        if f.is_file()
    ] + ["docusaurus.config.js", "sidebars.js", "package.json", "nginx.conf"]
    assert any(p.startswith("docs/") for p in inputs) and any(p.startswith("src/") for p in inputs)
    assert [p for p in inputs if _ignored(rules, p)] == []
    # Secrets, dependencies, build output and local data stay out of the build context (C4).
    for path in (".env", ".env.local", "node_modules/x/index.js", "build/index.html", ".git/HEAD",
                 "data/app.db", "backups/dump.sql", "logs/app.log",
                 # root-level files: only the suffix rules catch these (closing pass 3, Sonnet)
                 "local.db", "cache.sqlite", "debug.log"):  # fmt: skip
        assert _ignored(rules, path), path


def test_matcher_reads_the_spellings_the_guard_must_catch() -> None:
    # The guard above is only as good as `_ignored`: each spelling of "drop the docs" must match.
    for rule in ("docs", "/docs", "./docs", "docs/", "docs/**", "docs/*", "**/docs", "[d]ocs",
                 "**/*.md", "**/intro.md"):  # fmt: skip
        assert _ignored([rule], "docs/intro.md"), rule
    # Docker anchors a pattern at the context root: `*.md` drops README.md, not docs/intro.md.
    assert _ignored(["*.md"], "README.md") and not _ignored(["*.md"], "docs/intro.md")
    assert _ignored(["**/package.json"], "package.json") and _ignored(["**/*.md"], "README.md")
    assert not _ignored(["*.md"], "src/pages/index.js")
    # A `!` rule re-includes and the last matching rule wins, as in Docker (Finish review C4).
    assert not _ignored(["docs", "!docs/intro.md"], "docs/intro.md")
    assert _ignored(["!docs/intro.md", "docs"], "docs/intro.md")


def test_scaffold_does_not_publish_the_internal_docs_trees(scaffolded: Path) -> None:
    # The scaffold and the governance sync fill docs/reference, docs/development, docs/operations
    # and docs/archive with internal Fabrik material (the operator's AI vendor access notes, the
    # /opt project catalog with every dev URL). Docusaurus publishes the whole docs/ tree, so each
    # of those files must fall under a content-docs exclude (closing pass C1).
    from fabrik.scaffold import _DOCUSAURUS_UNPUBLISHED_DIRS

    cfg = (scaffolded / "docusaurus.config.js").read_text()
    start = cfg.index("exclude: [")
    excludes = re.findall(r"'([^']+)'", cfg[start : cfg.index("]", start)])
    for d in _DOCUSAURUS_UNPUBLISHED_DIRS:
        assert f"{d}/**" in excludes, d
    nested = [
        f.relative_to(scaffolded / "docs").as_posix()
        for f in (scaffolded / "docs").rglob("*.md")
        if f.parent != scaffolded / "docs"
    ]
    assert "reference/kilo/AI_VENDOR_ACCESS.md" in nested, nested
    assert [p for p in nested if p.split("/", 1)[0] not in _DOCUSAURUS_UNPUBLISHED_DIRS] == []


def test_every_synced_docs_subtree_is_unpublished() -> None:
    # The sync adds files after the scaffold, so the scaffold's own tree is not the whole list: every
    # docs/ subtree the governance sync writes must be unpublished as well.
    import importlib.util

    from fabrik.scaffold import _DOCUSAURUS_UNPUBLISHED_DIRS, _DOCUSAURUS_UNPUBLISHED_DOCS

    spec = importlib.util.spec_from_file_location(
        "manifest", REPO_ROOT / "scripts" / "fabrik_synced_manifest.py"
    )
    assert spec and spec.loader
    manifest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(manifest)
    # Every docs/ DESTINATION the sync writes: the second half of each (source, dest) pair, and each
    # plain path in a directory list — read from the manifest's own module-level collections, so a
    # hub-side source path such as docs/PROJECT_CATALOG.md is never mistaken for a destination.
    dests: set[str] = set()
    for value in vars(manifest).values():
        if not isinstance(value, (list, tuple, set, frozenset)):
            continue
        for item in value:
            dest = item[1] if isinstance(item, tuple) and len(item) == 2 else item
            if isinstance(dest, str) and dest.startswith("docs/"):
                dests.add(dest.removeprefix("docs/"))
    nested = {d.split("/", 1)[0] for d in dests if "/" in d}
    top_files = {d for d in dests if "/" not in d}
    assert "reference" in nested and "DECISIONS.md" in top_files, dests
    assert nested <= set(_DOCUSAURUS_UNPUBLISHED_DIRS), nested - set(_DOCUSAURUS_UNPUBLISHED_DIRS)
    # A top-level docs/*.md the sync writes must be unpublished by name (closing pass 3, item 3).
    assert top_files <= set(_DOCUSAURUS_UNPUBLISHED_DOCS), top_files - set(
        _DOCUSAURUS_UNPUBLISHED_DOCS
    )


def test_every_governed_docs_subtree_is_published_or_not_by_decision() -> None:
    # The pipeline writes into docs/ subtrees the sync never names (specs and plans under
    # superpowers/, box notes under workstation/). check_structure.py lists every subtree the
    # governance allows, so each is either unpublished or one of the site's own content homes —
    # a new subtree fails here until someone decides which (closing pass 3, item 1).
    import importlib.util

    from fabrik.scaffold import _DOCUSAURUS_UNPUBLISHED_DIRS

    spec = importlib.util.spec_from_file_location(
        "check_structure", REPO_ROOT / "scripts" / "enforcement" / "check_structure.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    published = {"guides", "user-guide"}
    governed = set(module.VALID_DOCS_SUBDIRS)
    assert "superpowers" in governed, governed
    assert governed - published == set(_DOCUSAURUS_UNPUBLISHED_DIRS), (
        governed - published - set(_DOCUSAURUS_UNPUBLISHED_DIRS),
        set(_DOCUSAURUS_UNPUBLISHED_DIRS) - governed,
    )


def test_engines_floor_follows_the_registry_through_both_emitters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A literal ">=22" in package.json.j2 passes while the registry happens to say "22"; a
    # different floor proves the value is rendered, not hard-coded (Phase B review S2).
    import json

    from fabrik.scaffold import create_project

    monkeypatch.setattr(
        version_registry, "VERSIONS_FILE", _registry(tmp_path, {**GOOD, "node_engines_floor": "18"})
    )
    project = create_project(
        name="docs-floor",
        description="x",
        base=tmp_path,
        project_type="docusaurus",
        generate_spec=False,
    )
    assert json.loads((project / "package.json").read_text())["engines"]["node"] == ">=18"
    rendered = TemplateRenderer(output_dir=tmp_path / "out").render(
        _spec(tmp_path, "docusaurus", spec_id="docs-floor"), dry_run=True
    )
    assert json.loads(rendered["package.json"])["engines"]["node"] == ">=18"


# ── Phase C: one real build, opt-in (FABRIK_REAL_DOCKER_BUILD=1) ────────────


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:  # type: ignore[override]
        return None


def _get(url: str, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with opener.open(req, timeout=10) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, {k.lower(): v for k, v in err.headers.items()}, err.read()


def _docker(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=timeout, check=False
    )


@pytest.mark.skipif(
    os.environ.get("FABRIK_REAL_DOCKER_BUILD") != "1",
    reason="opt-in: set FABRIK_REAL_DOCKER_BUILD=1 to build and run a scaffolded docusaurus image",
)
def test_real_build_serves_the_static_site(tmp_path: Path) -> None:
    from fabrik.scaffold import create_project

    if shutil.which("docker") is None:
        pytest.fail("FABRIK_REAL_DOCKER_BUILD=1 but docker is not installed")
    project = create_project(
        name="docs-real",
        description="x",
        base=tmp_path,
        project_type="docusaurus",
        generate_spec=False,
    )
    assert not (project / "package-lock.json").exists()
    tag = f"fabrik-docusaurus-probe:{uuid.uuid4().hex[:12]}"
    name = f"fabrik-docusaurus-probe-{uuid.uuid4().hex[:8]}"
    try:
        build = _docker("build", "-t", tag, str(project), timeout=900)
        assert build.returncode == 0, build.stdout[-3000:] + build.stderr[-3000:]
        run = _docker("run", "-d", "--rm", "--name", name, "-p", "127.0.0.1::80", tag)
        assert run.returncode == 0, run.stderr
        port = _docker("port", name, "80").stdout.strip().splitlines()[0].rsplit(":", 1)[1]
        base = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 60
        while True:
            try:
                status, _, _ = _get(f"{base}/docs/intro/")
                if status == 200:
                    break
            except OSError:
                pass
            assert time.monotonic() < deadline, "the container never served /docs/intro/"
            time.sleep(1)

        status, headers, body = _get(f"{base}/docs/intro/")
        assert status == 200
        assert headers.get("cache-control") == "no-cache", headers  # pages revalidate (D-664)
        html = body.decode()
        assert "pagefind-modal-trigger" in html
        assert 'type="module"' in html and "/pagefind/pagefind-component-ui.js" in html

        # The pack's lookup serves docs/intro/index.html for the slashless path itself: no
        # redirect, so no http:// Location to leak past Traefik.
        status, headers, _ = _get(f"{base}/docs/intro")
        assert status == 200 and "location" not in headers, (status, headers)

        status, _, _ = _get(f"{base}/pagefind/pagefind-component-ui.js")
        assert status == 200

        # The internal docs trees never reach the site (D-481): the sitemap Docusaurus writes names
        # every published page, and none sits under an unpublished tree.
        status, _, sitemap = _get(f"{base}/sitemap.xml")
        assert status == 200 and b"/docs/intro" in sitemap, sitemap[:500]
        for tree in (
            b"/docs/reference/",
            b"/docs/development/",
            b"/docs/operations/",
            b"/docs/archive/",
        ):
            assert tree not in sitemap, tree

        # A missing page answers 404 with the build's own 404.html, never the landing page.
        status, _, body404 = _get(f"{base}/no/such/page")
        assert status == 404 and b"Page Not Found" in body404, (status, body404[:300])
        assert b"nginx" not in body404, "nginx's stock 404 page, not the build's 404.html"

        asset = next(m for m in re.findall(r'src="(/assets/js/[^"]+\.js)"', html))
        status, headers, _ = _get(f"{base}{asset}", {"Accept-Encoding": "gzip"})
        assert status == 200
        assert headers.get("cache-control") == "public, max-age=31536000, immutable", headers
        assert headers.get("content-encoding") == "gzip", headers
    finally:
        _docker("rm", "-f", name)
        _docker("rmi", "-f", tag)
