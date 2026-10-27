"""W-6eb61fa0: TemplateRenderer must not HTML-escape what it renders.

`select_autoescape(["yaml", "yml", "j2"])` matched every `*.j2` name, so compose files, Dockerfiles,
JS and env lines came out HTML-escaped: a template-sourced secret `p&ss` deployed as `p&amp;ss`. No
template emits HTML, so the renderer renders verbatim. Scope: the five characters HTML escaping
rewrote (`& < > ' "`). Env-value quoting (`"`, newlines, `$`, ` #`, `: `) is graded by
tests/test_compose_env_quoting.py (W-80aed026).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from jinja2 import nodes

from fabrik.spec_loader import Spec, load_spec
from fabrik.template_renderer import TemplateRenderer

REPO = Path(__file__).resolve().parent.parent
# The characters autoescape rewrote, minus `"` (graded with the other quoting cases in test_compose_env_quoting.py).
TRICKY = "a&b<c>d'e"

# The compose templates that write every env/secret value into `environment:` (`KEY=value`).
ENV_TEMPLATES = [
    "node-api",
    "python-api",
    "saas-skeleton",
    "static-site",
    "file-api",
    "file-worker",
    "chrome-extension",
]


def _service_env(compose: str, service: str | None = None) -> dict[str, str | None]:
    """`service` None = the first service, the app's (chrome-extension names it `<id>-backend`)."""
    services = yaml.safe_load(compose)["services"]
    env = services[service or next(iter(services))].get("environment") or []
    if isinstance(env, dict):
        return {k: (None if v is None else str(v)) for k, v in env.items()}
    out: dict[str, str | None] = {}
    for item in env:
        key, sep, value = str(item).partition("=")
        out[key] = value if sep else None  # a bare `- KEY` passes the host's value through
    return out


def _spec(template: str, **extra: object) -> Spec:
    return Spec.model_validate(
        {
            "id": "demo-svc",
            "template": template,
            "domain": "demo.vps1.ocoron.com",
            "env": {"PLAIN_SETTING": TRICKY},
            "resources": {"memory": "512M", "cpu": "0.5"},
            **extra,
        }
    )


@pytest.mark.parametrize("template", ENV_TEMPLATES)
def test_env_and_secret_values_reach_compose_unescaped(template: str) -> None:
    compose = TemplateRenderer().render(
        _spec(template), secrets={"SOME_SECRET": TRICKY}, dry_run=True
    )["compose.yaml"]
    env = _service_env(compose)
    assert env.get("SOME_SECRET") == TRICKY, compose
    assert env.get("PLAIN_SETTING") == TRICKY, compose


COMPANION_TEMPLATES = sorted(
    p.parent.name
    for p in (REPO / "templates").glob("*/compose.yaml.j2")
    if "_companion_service" in p.read_text(encoding="utf-8")
)


@pytest.mark.parametrize("template", COMPANION_TEMPLATES)
def test_a_companion_service_gets_its_env_and_overrides_unescaped(template: str) -> None:
    spec = _spec(
        template,
        companion_services=[
            {
                "id": "demo-svc-worker",
                "command": ["node", "worker.js"],
                "memory": "256M",
                "env_overrides": {"WORKER_SETTING": TRICKY},
            }
        ],
    )
    compose = TemplateRenderer().render(spec, secrets={"SOME_SECRET": TRICKY}, dry_run=True)[
        "compose.yaml"
    ]
    env = _service_env(compose, "demo-svc-worker")
    assert env.get("SOME_SECRET") == TRICKY, compose
    assert env.get("WORKER_SETTING") == TRICKY, compose


def test_the_renderer_environment_never_autoescapes() -> None:
    """Catches any autoescape that comes back, a `select_autoescape` callable for SOME suffixes included."""
    assert TemplateRenderer().jinja.autoescape is False


# The built-in filters that HTML-escape their input (`xmlattr` and `urlize` call markupsafe's escape).
# `tojson` is not one: its `&`-style escapes are JSON string escapes, which every JSON or YAML
# reader decodes back (`_partials/_companion_service.yaml.j2` relies on that for `command:`).
_ESCAPE_FILTERS = {"e", "escape", "forceescape", "xmlattr", "urlize"}


def _escapes_by_filter(n: nodes.Filter) -> bool:
    if n.name in _ESCAPE_FILTERS:
        return True
    # `map("e")` applies the filter its positional arguments name, `map("map", "e")` included, so any
    # escape name among them is flagged, and so is a name only known at render time (`map(name)`,
    # `map(*names)`); a constant name outside `_ESCAPE_FILTERS` (`map("upper")`) is not.
    if n.name == "map":
        return n.dyn_args is not None or any(
            not isinstance(a, nodes.Const) or a.value in _ESCAPE_FILTERS for a in n.args
        )
    return False


def _escapes(source: str) -> list[str]:
    """Escape routes in a template, read from Jinja's own parse tree (W-27634d4e).

    A regex over `{{ }}`/`{% %}` spans misread comments, `{% raw %}` blocks and a `}}`/`%}` inside a
    string or dict literal; the parser does not. `nodes.Filter` covers the pipe form, `{% filter %}`
    blocks and `{% set x | e %}`; an `{% autoescape %}` block is a scoped eval-context modifier, flagged
    unless its value is a falsy constant (`false`, `0`, `none`, `""`) — `not true` is flagged too. Not modelled: a file the scan below does not read, reached
    through `{% include %}`/`{% import %}` (today every such tag in the files it reads names
    `_partials/`, which it reads).
    """
    tree = TemplateRenderer().jinja.parse(source)
    hits = [f"{n.lineno}: |{n.name}" for n in tree.find_all(nodes.Filter) if _escapes_by_filter(n)]
    hits += [
        f"{n.lineno}: autoescape block"
        for n in tree.find_all(nodes.EvalContextModifier)
        for k in n.options
        if k.key == "autoescape" and not (isinstance(k.value, nodes.Const) and not k.value.value)
    ]
    return hits


@pytest.mark.parametrize(
    ("source", "escapes"),
    [
        ("{{ x | e }}", True),
        ("{% filter escape %}x{% endfilter %}", True),
        ("{% autoescape true %}{{ x }}{% endautoescape %}", True),
        ("{% set y | forceescape %}x{% endset %}", True),
        # An unbalanced `{{` in a comment or a raw block must not swallow (and hide) the next line.
        ("{# a {{ b #}\n{% filter escape %}x{% endfilter %}{{ y }}", True),
        ("{% raw %}{{{% endraw %}\n{% filter escape %}x{% endfilter %}{{ y }}", True),
        # A `}}` inside a string or dict literal must not end the expression early.
        ('{{ "}}" | e }}', True),
        ("{{ {'k': '}}'} | e }}", True),
        # A filter applied by name, and the built-ins that escape internally.
        ('{{ xs | map("e") | join }}', True),
        ("{{ xs | map(name) | join }}", True),
        ("{{ xs | map(*names) | join }}", True),
        ('{{ [xs] | map("map", "e") | map("join") | join }}', True),
        ("{{ {'a': x} | xmlattr }}", True),
        ("{{ x | urlize }}", True),
        ("{% autoescape flag %}{{ x }}{% endautoescape %}", True),
        # Not an escape: a block that turns escaping off, JSON encoding, `map` over an attribute.
        ("{% autoescape false %}{{ x }}{% endautoescape %}", False),
        ("{{ x | tojson }}", False),
        ('{{ xs | map(attribute="name") | join }}', False),
        ('{{ xs | map("upper") | join }}', False),
        # Not Jinja: JS `||`, a comment, a raw block, a string.
        ("const a = b || e;", False),
        ("{# {{ x | e }} #}", False),
        ("{% raw %}{{ x | e }}{% endraw %}", False),
        ('{{ "| e" }}', False),
    ],
)
def test_the_escape_scan(source: str, escapes: bool) -> None:
    assert bool(_escapes(source)) is escapes


def test_no_renderer_template_escapes_on_its_own() -> None:
    """The template-side escape routes the environment flag cannot see: blocks and filters."""
    hits: list[str] = []
    scanned = 0
    for d in sorted((REPO / "templates").iterdir()):
        if not (d / "compose.yaml.j2").exists() and d.name != "_partials":
            continue
        for f in sorted(d.rglob("*.j2")):
            scanned += 1
            hits += [f"{f.relative_to(REPO)}:{h}" for h in _escapes(f.read_text(encoding="utf-8"))]
    assert scanned > 0
    assert not hits, hits


def test_a_quoted_spec_command_renders_its_quotes() -> None:
    """zitadel's spec is the live case (its deploy takes the docker-source path, not this renderer).

    The command is a double-quoted YAML scalar since W-ff313a14, so its `"` is `\\"` in the text: the
    parsed value is the check (an HTML-escaped `&quot;` would fail it the same way).
    """
    spec = load_spec(REPO / "specs" / "services" / "zitadel.yaml")
    compose = TemplateRenderer().render(spec, dry_run=True)["compose.yaml"]
    command = yaml.safe_load(compose)["services"]["zitadel"]["command"]
    assert command == spec.source.image_command
    assert '--masterkey "${ZITADEL_MASTERKEY}"' in command
