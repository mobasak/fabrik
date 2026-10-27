"""W-6eb61fa0: TemplateRenderer must not HTML-escape what it renders.

`select_autoescape(["yaml", "yml", "j2"])` matched every `*.j2` name, so compose files, Dockerfiles,
JS and env lines came out HTML-escaped: a template-sourced secret `p&ss` deployed as `p&amp;ss`. No
template emits HTML, so the renderer renders verbatim. Scope: the five characters HTML escaping
rewrote (`& < > ' "`). Env-value quoting (`"`, newlines, `$`, ` #`, `: `) is graded by
tests/test_compose_env_quoting.py (W-80aed026).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

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


# Only Jinja code is scanned (`|| e` in plain JS is not a filter), whole-file so a tag split across
# lines is one span. Not modelled: a `}}`/`%}` inside a string literal in a tag, which ends the span early.
_JINJA_SPAN = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.DOTALL)
_ESCAPE_IN_SPAN = re.compile(
    r"^\{%[-+]?\s*(?:autoescape|filter\s+(?:e|escape|forceescape))\b"  # block forms
    r"|\|\s*(?:e|escape|forceescape)\b"  # the pipe-filter form
)


def test_no_renderer_template_escapes_on_its_own() -> None:
    """The template-side escape routes the environment flag cannot see: blocks and filters."""
    hits: list[str] = []
    scanned = 0
    for d in sorted((REPO / "templates").iterdir()):
        if not (d / "compose.yaml.j2").exists() and d.name != "_partials":
            continue
        for f in sorted(d.rglob("*.j2")):
            scanned += 1
            text = f.read_text(encoding="utf-8")
            for m in _JINJA_SPAN.finditer(text):
                if _ESCAPE_IN_SPAN.search(m.group()):
                    line = text.count("\n", 0, m.start()) + 1
                    hits.append(f"{f.relative_to(REPO)}:{line}: {m.group()}")
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
