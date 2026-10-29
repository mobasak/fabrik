"""W-80aed026: every templated compose env item is an ASCII YAML double-quoted scalar holding the exact value.

The env items used to be plain scalars `- KEY=value`: a `"` deployed as a literal `\\"` (env_escape's backslash
nothing removed), a newline broke the list where no filter ran (file-api, file-worker), ` #` cut the value as a
comment, `: ` turned the item into a mapping, and a `$` in a secret was compose-interpolated. Spec `env:` values
keep compose interpolation on purpose (`${DATABASE_URL}` in 20+ specs), so only the secrets layer gets `$` → `$$`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from jinja2 import meta

from fabrik.spec_loader import Spec
from fabrik.template_renderer import TemplateRenderer

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = REPO / "templates"

# The compose templates that write env/secret values into `environment:`.
ENV_TEMPLATES = sorted(
    p.parent.name
    for p in TEMPLATES.glob("*/compose.yaml.j2")
    if "env.items()" in p.read_text(encoding="utf-8")
)
COMPANION_TEMPLATES = sorted(
    p.parent.name
    for p in TEMPLATES.glob("*/compose.yaml.j2")
    if "_companion_service" in p.read_text(encoding="utf-8")
)
# The keys file-api and file-worker emit through a fixed `- KEY=... env.get(...)` line, not the loop.
FIXED_KEYS = {"file-api": "LOG_LEVEL", "file-worker": "WORKER_ID"}

# Each value broke a plain scalar or env_escape in its own way; the rest are YAML-escape edge cases.
TRICKY = {
    "dquote": 'a"b',
    "newline": "l1\nl2",
    "hash": "x #y",
    "colon": "k: v",
    "squote": "' q'",
    "backslash": "a\\b",
    "tab": "a\tb",
    "del": "a\x7fb",
    "linesep": "a\u2028b",
    "nonascii": "caf\u00e9 \u00a0\U0001f600",
    "long": "x" * 300,
    # PyYAML folds a double-quoted scalar only at a space, so this one is what width=sys.maxsize guards.
    "long_spaced": "word " * 60,
    "lead_trail": "  pad  ",
    "dashes": "- item",
}


def _service_env(compose: str, service: str | None = None) -> dict[str, str | None]:
    services = yaml.safe_load(compose)["services"]
    env = services[service or next(iter(services))].get("environment") or []
    assert isinstance(env, list), env
    out: dict[str, str | None] = {}
    for item in env:
        assert isinstance(item, str), f"env item parsed as {type(item).__name__}: {item!r}"
        key, sep, value = item.partition("=")
        out[key] = value if sep else None
    return out


def _spec(template: str, env: dict[str, str], **extra: object) -> Spec:
    return Spec.model_validate(
        {
            "id": "demo-svc",
            "template": template,
            "domain": "demo.vps1.ocoron.com",
            "env": env,
            "resources": {"memory": "512M", "cpu": "0.5"},
            **extra,
        }
    )


def _render(spec: Spec, secrets: dict[str, str]) -> str:
    return TemplateRenderer().render(spec, secrets=secrets, dry_run=True)["compose.yaml"]


def test_the_template_populations_are_not_empty() -> None:
    assert len(ENV_TEMPLATES) >= 7, ENV_TEMPLATES
    assert COMPANION_TEMPLATES, COMPANION_TEMPLATES


@pytest.mark.parametrize("name", sorted(TRICKY))
@pytest.mark.parametrize("template", ENV_TEMPLATES)
def test_compose_env_value_round_trips(template: str, name: str) -> None:
    value = TRICKY[name]
    env = {"PLAIN_SETTING": value}
    fixed = FIXED_KEYS.get(template)
    if fixed:
        env[fixed] = value
    compose = _render(_spec(template, env), {"SOME_SECRET": value})
    # The deployer writes compose with the locale encoding, so the emitted items stay ASCII (template
    # comments are the template's own text).
    items = [ln for ln in compose.splitlines() if ln.lstrip().startswith('- "') and "=" in ln]
    assert items and all(ln.isascii() for ln in items), items
    got = _service_env(compose)
    assert got.get("PLAIN_SETTING") == value, compose
    assert got.get("SOME_SECRET") == value, compose
    if fixed:
        assert got.get(fixed) == value, compose


@pytest.mark.parametrize("template", COMPANION_TEMPLATES)
def test_companion_env_and_overrides_round_trip(template: str) -> None:
    value = 'q"1 #c: d\nl2'
    spec = _spec(
        template,
        {"PLAIN_SETTING": value},
        companion_services=[
            {
                "id": "demo-svc-worker",
                "command": ["node", "worker.js"],
                "memory": "256M",
                "env_overrides": {"WORKER_SETTING": value, "OVR_DSN": "${DATABASE_URL}"},
            }
        ],
    )
    got = _service_env(_render(spec, {"SOME_SECRET": value + "$"}), "demo-svc-worker")
    assert got.get("PLAIN_SETTING") == value
    assert got.get("SOME_SECRET") == value + "$$"
    assert got.get("WORKER_SETTING") == value
    assert got.get("OVR_DSN") == "${DATABASE_URL}"  # env_overrides are spec values: interpolated


@pytest.mark.parametrize("template", ENV_TEMPLATES)
def test_secret_dollar_is_literal(template: str) -> None:
    """compose reads `$$` as one literal `$`; a lone `$` in a secret would be interpolated."""
    secrets = {"SOME_SECRET": "p$ss${X}$$"}
    fixed = FIXED_KEYS.get(template)
    if fixed:
        secrets[fixed] = "w$1"
    got = _service_env(_render(_spec(template, {}), secrets))
    assert got.get("SOME_SECRET") == "p$$ss$${X}$$$$"
    if fixed:
        assert got.get(fixed) == "w$$1"


@pytest.mark.parametrize("template", ENV_TEMPLATES)
def test_secret_wins_and_is_escaped(template: str) -> None:
    """A key in both spec env and secrets takes the secret (the merge order) — escaped as a secret."""
    got = _service_env(_render(_spec(template, {"SHARED": "${FROM_SPEC}"}), {"SHARED": "s$cret"}))
    assert got.get("SHARED") == "s$$cret"


def test_render_does_not_mutate_secrets() -> None:
    secrets = {"SOME_SECRET": "p$ss"}
    _render(_spec("python-api", {}), secrets)
    assert secrets == {"SOME_SECRET": "p$ss"}


@pytest.mark.parametrize("template", ENV_TEMPLATES)
def test_spec_env_interpolation_kept(template: str) -> None:
    """Specs put `${VAR}` in `env:` on purpose (evolution-api's DATABASE_CONNECTION_URI: ${DATABASE_URL})."""
    got = _service_env(_render(_spec(template, {"DSN": "${DATABASE_URL}"}), {}))
    assert got.get("DSN") == "${DATABASE_URL}"


@pytest.mark.parametrize("bad", ["sec\x00ret", "sec\udc80ret"], ids=["nul", "lone-surrogate"])
@pytest.mark.parametrize("layer", ["secret", "spec"])
def test_unrepresentable_value_refused(bad: str, layer: str) -> None:
    """runc refuses a NUL in env and compose refuses an escaped lone surrogate, so render fails first —
    naming the key, never the value (render errors are echoed and logged)."""
    spec_env, secrets = ({}, {"SOME_KEY": bad}) if layer == "secret" else ({"SOME_KEY": bad}, {})
    with pytest.raises(ValueError, match="SOME_KEY") as exc:
        _render(_spec("python-api", spec_env), secrets)
    assert "sec" not in str(exc.value)


# --- W-ff313a14: compose scalars outside `environment:` ------------------------------------------------------

ZITADEL_COMMAND = 'start-from-init --masterkey "${ZITADEL_MASTERKEY}" --tlsMode external'


def _service(compose: str, service: str = "demo-svc") -> dict:
    return yaml.safe_load(compose)["services"][service]


@pytest.mark.parametrize(
    "value", [*TRICKY.values(), ZITADEL_COMMAND, "--port 80"], ids=[*TRICKY, "zitadel", "smoke"]
)
def test_image_command_round_trips(value: str) -> None:
    """The YAML `command` value is the spec string, `$` kept for compose interpolation (zitadel)."""
    source = {"image": "busybox:1", "image_command": value}
    compose = _render(_spec("python-api", {}, source=source), {})
    assert _service(compose)["command"] == value, compose


@pytest.mark.parametrize("bad", ["sec\x00ret", "sec\udc80ret"], ids=["nul", "lone-surrogate"])
@pytest.mark.parametrize("field", ["image_command", "health.test", "companion command"])
def test_compose_str_refuses_unrepresentable_naming_the_field(bad: str, field: str) -> None:
    """`compose_str` refuses what compose or runc cannot hold, naming the field and never the value."""
    if field == "image_command":
        spec = _spec("python-api", {}, source={"image": "busybox:1", "image_command": bad})
    elif field == "health.test":
        spec = _spec("python-api", {}, health={"test": ["CMD-SHELL", bad]})
    else:
        companion = {"id": "demo-svc-worker", "command": ["node", bad], "memory": "256M"}
        spec = _spec("python-api", {}, companion_services=[companion])
    with pytest.raises(ValueError, match=field.replace(".", r"\.")) as exc:
        _render(spec, {})
    assert "sec" not in str(exc.value)


@pytest.mark.parametrize("name", sorted(TRICKY))
def test_health_test_round_trips(name: str) -> None:
    test = ["CMD-SHELL", TRICKY[name], "x"]
    compose = _render(_spec("python-api", {}, health={"test": test}), {})
    assert _service(compose)["healthcheck"]["test"] == test, compose


@pytest.mark.parametrize("template", COMPANION_TEMPLATES)
def test_companion_command_round_trips(template: str) -> None:
    """`tojson` wrote a non-BMP character as a JSON surrogate pair, which YAML reads as two lone surrogates."""
    command = ["node", TRICKY["nonascii"], TRICKY["dquote"], TRICKY["backslash"]]
    companion = {"id": "demo-svc-worker", "command": command, "memory": "256M"}
    compose = _render(_spec(template, {}, companion_services=[companion]), {})
    assert _service(compose, "demo-svc-worker")["command"] == command, compose


@pytest.mark.parametrize(
    "port", ["3000", "8", "1", "65535", "${APP_PORT}", "${APP_PORT:-3000}", "${APP_PORT:-65535}"]
)
def test_file_api_port_round_trips(port: str) -> None:
    spec = _spec("file-api", {"PORT": port}, health={"path": "/api/health"})
    svc = _service(_render(spec, {}))
    assert svc["healthcheck"]["test"][-1] == f"http://localhost:{port}/api/health"
    assert f"traefik.http.services.demo-svc.loadbalancer.server.port={port}" in svc["labels"]


@pytest.mark.parametrize(
    "port",
    [
        '3000" x',
        "30 #00",
        "3000: x",
        "${A}x",
        "${A:-x}",
        "",
        "123456",
        "$${A}",
        # Unicode decimal digits that a `\d` pattern admits (review A-1), and the range edges (A-2).
        "３０００",
        "٣٠٠٠",
        "${A:-٣}",
        "0",
        "00000",
        "65536",
        "99999",
        "${A:-0}",
        "${A:-65536}",
    ],
)
@pytest.mark.parametrize("site", ["label", "healthcheck"])
def test_file_api_port_refused(port: str, site: str) -> None:
    """Each PORT site on its own accepts only a port number or a compose interpolation: the label renders
    with no health block, the healthcheck with no HTTP exposure (review C-1)."""
    if site == "label":
        spec = _spec("file-api", {"PORT": port})
    else:
        spec = _spec(
            "file-api", {"PORT": port}, health={"path": "/h"}, expose={"http": False}, domain=None
        )
    compose_without_port = _render(spec.model_copy(update={"env": {}}), {})
    assert ("loadbalancer.server.port=" in compose_without_port) is (site == "label")
    assert ("healthcheck:" in compose_without_port) is (site == "healthcheck")
    with pytest.raises(ValueError, match="PORT"):
        _render(spec, {})


_BAD_HEALTH_PATHS = [
    '/h"x',
    "/h x",
    "/h#x",
    "/h$x",
    "/h{x}",
    "/h'x",
    "/h\\x",
    "/h`x`",
    "health",
    "",
]


@pytest.mark.parametrize("path", _BAD_HEALTH_PATHS)
def test_health_path_outside_grammar_refused(path: str) -> None:
    from pydantic import ValidationError

    from fabrik.orchestrator.exceptions import ValidationError as ApplyError
    from fabrik.orchestrator.validator import SpecValidator

    with pytest.raises(ValidationError, match="health"):
        _spec("node-api", {}, health={"path": path})
    raw = {
        "name": "demo-svc",
        "template": "node-api",
        "domain": "demo.vps1.ocoron.com",
        "health": {"path": path},
    }
    with pytest.raises(ApplyError, match="health"):
        SpecValidator(templates_dir=TEMPLATES).validate(raw)


def test_health_path_query_is_shell_quoted() -> None:
    """`&` and `;` are legal in a health path and are shell syntax, so both CMD-SHELL probes single-quote the URL."""
    from fabrik.orchestrator.deployer_ssh import _generate_docker_compose

    path = "/health?a=1&b=(2);c"
    url = f"http://localhost:8000{path}"
    compose = _render(_spec("python-api", {}, health={"path": path}), {})
    probe = _service(compose)["healthcheck"]["test"][1]
    assert probe.count(f"'{url}'") == 2, probe
    docker = _generate_docker_compose("demo-svc", "busybox:1", 8000, "", {"health": {"path": path}})
    probe = _service(docker)["healthcheck"]["test"][1]
    assert f"'{url}'" in probe, probe
    exec_form = _service(_render(_spec("node-api", {}, health={"path": path}), {}))
    assert exec_form["healthcheck"]["test"][-1] == f"http://localhost:3000{path}"


def test_every_service_spec_passes_the_new_grammars() -> None:
    from fabrik.orchestrator.validator import SpecValidator
    from fabrik.spec_loader import load_spec

    validator = SpecValidator(templates_dir=TEMPLATES)
    specs = sorted((REPO / "specs" / "services").glob("*.yaml"))
    assert len(specs) >= 60, len(specs)
    for f in specs:
        load_spec(f)
        validator.validate(validator.load_spec(f))


def _raw_apply_spec(**extra: object) -> dict:
    return {"name": "demo-svc", "template": "python-api", "domain": "demo.vps1.ocoron.com", **extra}


@pytest.mark.parametrize("name", ["x}#", "a-b", "main\n", 7])
def test_apply_validator_refuses_a_bad_database_name(name: object) -> None:
    """The apply path loads a raw dict: a bad name is refused at step 1, before DNS (review A2-1)."""
    from fabrik.orchestrator.exceptions import ValidationError as ApplyError
    from fabrik.orchestrator.validator import SpecValidator

    with pytest.raises(ApplyError, match="depends.postgres"):
        SpecValidator(templates_dir=TEMPLATES).validate(_raw_apply_spec(depends={"postgres": name}))


@pytest.mark.parametrize("port", ["80'; id; '", "８０８０", "0", " 80", 0, 65536, True, 8.5])
def test_apply_validator_refuses_a_bad_image_port(port: object) -> None:
    """The docker-image writer pastes `image_port` into its shell probe and traefik label (review A2-2)."""
    from fabrik.orchestrator.exceptions import ValidationError as ApplyError
    from fabrik.orchestrator.validator import SpecValidator

    raw = _raw_apply_spec(source={"type": "docker", "image": "busybox:1", "image_port": port})
    with pytest.raises(ApplyError, match="image_port"):
        SpecValidator(templates_dir=TEMPLATES).validate(raw)


def test_apply_validator_keeps_the_legitimate_values() -> None:
    from fabrik.orchestrator.validator import SpecValidator

    raw = _raw_apply_spec(
        depends={"postgres": "app_db"},
        source={"type": "docker", "image": "busybox:1", "image_port": 8080},
    )
    assert SpecValidator(templates_dir=TEMPLATES).validate(raw) is not None
    SpecValidator(templates_dir=TEMPLATES).validate(_raw_apply_spec(depends={"postgres": ""}))
    # A quoted port is the other spelling the load path's `Source.image_port` coerces (review pass 2).
    quoted = _raw_apply_spec(source={"type": "docker", "image": "busybox:1", "image_port": "8080"})
    SpecValidator(templates_dir=TEMPLATES).validate(quoted)


@pytest.mark.parametrize("name", ["db}x", "a #b", "x-y", "1db", "a" * 64, "d$b", "main\n"])
def test_depends_postgres_must_be_an_identifier(name: str) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="postgres"):
        _spec("python-api", {}, depends={"postgres": name})


def test_empty_depends_postgres_still_means_no_database() -> None:
    compose = _render(_spec("python-api", {}, depends={"postgres": ""}), {})
    assert "DATABASE_URL" not in _service_env(compose)


def test_database_url_default_round_trips() -> None:
    want = "${DATABASE_URL:-postgresql://postgres:${POSTGRES_PASSWORD}@postgres-main:5432/app_db}"
    rendered = []
    for template in sorted({*ENV_TEMPLATES, *COMPANION_TEMPLATES}):
        compose = _render(_spec(template, {}, depends={"postgres": "app_db"}), {})
        if "DATABASE_URL" in compose:
            rendered.append(template)
            assert _service_env(compose).get("DATABASE_URL") == want, (template, compose)
    # chrome-extension, node-api, python-api, saas-skeleton — the four with a DATABASE_URL default line.
    assert len(rendered) >= 4, rendered


# A templated env item is exactly `- {{ <key> | compose_env(<value>) }}`. Any other `- ` item whose key — names,
# hyphens and `{{ }}` tags in any mix, quoted or not, the quote closing before or after the `=` (`- {{ key }}=
# {{ value }}` was the old loop) — is followed by `=` and a `{{` or `{%` is an env value written by hand. A dotted key (a
# quoted traefik label) is not an env item, so not flagged; there is no other exemption (W-ff313a14).
# The tag may hold single braces (the DATABASE_URL default's `'${…:-' ~ … ~ '}'`), never a second tag.
_IN_TAG = r"(?:(?!\{\{|\}\}).)*"
_ENV_ITEM_LINE = re.compile(rf"^\s*-\s+\{{\{{{_IN_TAG}\|\s*compose_env\({_IN_TAG}\)\s*\}}\}}\s*$")
_TEMPLATED_KV_LINE = re.compile(r"^\s*-\s+[\"']?(?:[A-Za-z0-9_-]|\{\{[^{}]*\}\})+[\"']?=.*\{[{%]")


def _unquoted_env_line(line: str) -> bool:
    return not _ENV_ITEM_LINE.match(line) and bool(_TEMPLATED_KV_LINE.match(line))


@pytest.mark.parametrize(
    ("line", "unquoted"),
    [
        ("      - {{ key }}={{ value }}", True),
        ("      - {{ key }}={{ value | env_escape }}", True),
        ("      - FOO={{ env.get('FOO', 'x') }}", True),
        ('      - "{{ key }}={{ value }}"', True),
        ('      - "FOO={{ value }}"', True),
        ("      - {{ key }}={{ value | compose_env(x) }}", True),
        ("      - {{ key | compose_env(value) }}={{ other }}", True),
        ("      - {{ key | compose_env(value) }}", False),
        ("      - {{ 'FOO' | compose_env(env.get('FOO', 'x')) }}", False),
        ('      - "traefik.http.services.x.loadbalancer.server.port={{ p }}"', False),
        ("      - {{ vol.name }}:{{ vol.path }}", False),
        ("      - PYTHONUNBUFFERED=1", False),
        (
            "      - DATABASE_URL=${DATABASE_URL:-postgresql://postgres:${POSTGRES_PASSWORD}"
            "@postgres-main:5432/{{ depends.postgres }}}",
            True,
        ),
        ("      - DATABASE_URL={{ depends.postgres }}", True),
        ("      - DATABASE_URL=${DATABASE_URL:-{{ evil }}/{{ depends.postgres }}}", True),
        ('      - "{{ key }}"={{ value }}', True),
        ("      - '{{ key }}'={{ value }}", True),
        ("      - PREFIX_{{ key }}={{ value }}", True),
        ("      - {{ key }}_SUFFIX={{ value }}", True),
        ("      - MY-KEY={{ value }}", True),
        ("      - FOO={% if x %}1{% endif %}", True),
        ("      - {{ 'DATABASE_URL' | compose_env('${X:-' ~ depends.postgres ~ '}') }}", False),
    ],
)
def test_the_unquoted_env_line_matcher(line: str, unquoted: bool) -> None:
    assert _unquoted_env_line(line) is unquoted


def test_no_unquoted_env_line() -> None:
    hits: list[str] = []
    quoted = 0
    # YAML templates only: a markdown bullet (`preplan.md.j2`) is a `- ` line with `=` and `{{` too.
    yaml_templates = sorted({*TEMPLATES.rglob("*.yaml.j2"), *TEMPLATES.rglob("*.yml.j2")})
    assert yaml_templates, "no YAML template scanned"
    for f in yaml_templates:
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _unquoted_env_line(line):
                hits.append(f"{f.relative_to(REPO)}:{n}: {line.strip()}")
            quoted += bool(_ENV_ITEM_LINE.match(line))
    # 9 loops + 15 fixed lines + 5 DATABASE_URL defaults — the guard read the files it claims to.
    assert quoted >= 29, quoted
    assert not hits, hits


# A `command:` or `test:` whose value opens with a raw tag pastes spec text into a YAML scalar unquoted (the old
# `command: {{ spec.source.image_command }}` and `test: {{ health.test }}`); a tag routed through `compose_str`
# is the quoted form. A literal value that only embeds a tag (`sh -c "… {{ svc_port }}"`) is not this shape.
_RAW_SCALAR_TAG_LINE = re.compile(
    r"^\s*(?:command|test|entrypoint):(?:.*[\[,])?\s*[\"']?\{\{(?![^}]*\bcompose_str\b)"
)


@pytest.mark.parametrize(
    ("line", "raw"),
    [
        ("    command: {{ spec.source.image_command }}", True),
        ("      test: {{ health.test }}", True),
        ("    command: {{ c.command | tojson | safe }}", True),
        ("      test: [{{ x | join(', ') }}]", True),
        ('    command: "{{ spec.source.image_command }}"', True),
        ("    command: '{{ x }}'", True),
        ('      test: ["CMD-SHELL", {{ health.test }}]', True),
        ("    entrypoint: {{ x }}", True),
        (
            "    command: {{ spec.source.image_command | compose_str('source.image_command') }}",
            False,
        ),
        ("      test: [{{ health.test | map('compose_str', 'health.test') | join(', ') }}]", False),
        ('    command: sh -c "uvicorn app --port {{ svc_port }}"', False),
        ('      test: ["CMD", "curl", "-f", "http://localhost:3000{{ health.path }}"]', False),
    ],
)
def test_the_raw_scalar_tag_matcher(line: str, raw: bool) -> None:
    assert bool(_RAW_SCALAR_TAG_LINE.match(line)) is raw


def test_no_raw_command_or_test_tag() -> None:
    templates = sorted({*TEMPLATES.rglob("*.yaml.j2"), *TEMPLATES.rglob("*.yml.j2")})
    hits = [
        f"{f.relative_to(REPO)}:{n}: {line.strip()}"
        for f in templates
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
        if _RAW_SCALAR_TAG_LINE.match(line)
    ]
    assert not hits, hits


# render() $-escapes the secrets it hands to EVERY template as `env`; only compose output may read it.
# Jinja's own analysis decides what is a read (whitespace control `{{-env}}`, `x-env`, `env | tojson`
# all are; `spec.env`, `'.env'` and a template-local `set env` are not) — a regex only guesses at it.
_COMPOSE_NAMES = ("compose.yaml.j2", "_companion_service.yaml.j2")


def _reads_env(renderer: TemplateRenderer, source: str) -> bool:
    return "env" in meta.find_undeclared_variables(renderer.jinja.parse(source))


@pytest.mark.parametrize(
    ("code", "reads"),
    [
        ("{{ env }}", True),
        ("{{-env}}", True),
        ("{{ env-}}", True),
        ("{%-set e=env-%}", True),
        ("{{ x-env }}", True),
        ("{{ env | tojson }}", True),
        ("{{ env.get('X') }}", True),
        ("{% if 'X' in env %}x{% endif %}", True),
        ("{{ environment }}", False),
        ("{{ spec.env }}", False),
        ("{{ '.env' }}", False),
        ("{% set env = {} %}{{ env }}", False),
    ],
)
def test_the_env_read_check(tmp_path: Path, code: str, reads: bool) -> None:
    renderer = TemplateRenderer(templates_dir=TEMPLATES, output_dir=tmp_path)
    assert _reads_env(renderer, code) is reads


def test_only_compose_templates_read_env(tmp_path: Path) -> None:
    renderer = TemplateRenderer(templates_dir=TEMPLATES, output_dir=tmp_path)
    readers = {
        str(f.relative_to(REPO))
        for f in TEMPLATES.rglob("*.j2")
        if _reads_env(renderer, f.read_text(encoding="utf-8"))
    }
    compose = {r for r in readers if _is_compose_name(r)}
    assert len(compose) >= len(ENV_TEMPLATES), compose  # the check sees the reads it must
    assert readers == compose, sorted(readers - compose)


def _is_compose_name(reader: str) -> bool:
    return Path(reader).name in _COMPOSE_NAMES


@pytest.mark.parametrize(
    ("reader", "compose"),
    [
        ("templates/python-api/compose.yaml.j2", True),
        ("templates/_partials/_companion_service.yaml.j2", True),
        ("templates/x/docker-compose.yaml.j2", False),
        ("templates/x/my_companion_service.yaml.j2", False),
        ("templates/x/compose.yaml.j2.bak", False),
    ],
)
def test_compose_names_match_exactly(reader: str, compose: bool) -> None:
    assert _is_compose_name(reader) is compose


def _busybox_ready() -> bool:
    if not shutil.which("docker"):
        return False
    probe = subprocess.run(
        ["docker", "image", "inspect", "busybox"], capture_output=True, timeout=30, check=False
    )
    return probe.returncode == 0


@pytest.mark.skipif(
    not _busybox_ready(), reason="docker with a local busybox image is not available"
)
def test_started_container_sees_exact_values(tmp_path: Path) -> None:
    """The authority is compose itself: the started process's env, not a YAML re-read."""
    values = {**TRICKY, "dollar": "p$ss${HOME}$$x"}
    compose_env = TemplateRenderer().jinja.filters["compose_env"]
    lines = [
        f"      - {compose_env(f'V_{k.upper()}', v.replace('$', '$$'))}" for k, v in values.items()
    ]
    (tmp_path / "compose.yaml").write_text(
        "name: w80aed026-probe\nservices:\n  t:\n    image: busybox\n    network_mode: none\n"
        "    environment:\n" + "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    script = "; ".join(f"printf '%s\\0' \"$V_{k.upper()}\"" for k in values)
    res = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(tmp_path / "compose.yaml"),
            "run",
            "--rm",
            "--no-deps",
            "t",
            "sh",
            "-c",
            script,
        ],
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert res.returncode == 0, res.stderr.decode(errors="replace")
    got = res.stdout.decode("utf-8").split("\0")[:-1]
    assert got == list(values.values())
