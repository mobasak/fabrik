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


# A templated env list item (`- KEY=` with a `{{` on the line) must go through compose_env. Exempt: the
# literal `DATABASE_URL=${DATABASE_URL:-…/{{ depends.postgres }}}` default, whose only templated part is the
# spec's database name, not an env value (a separate quoting item, W-80aed026's OUT).
_UNQUOTED_ENV_LINE = re.compile(
    r"^\s*-\s+[A-Za-z_][A-Za-z0-9_]*=.*\{\{(?!\s*depends\.postgres\s*\}\}\}$)"
)
_ENV_ITEM_LINE = re.compile(r"^\s*-\s+\{\{.*\|\s*compose_env\(")


def test_no_unquoted_env_line() -> None:
    hits: list[str] = []
    quoted = 0
    for f in sorted(TEMPLATES.rglob("*.j2")):
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _UNQUOTED_ENV_LINE.match(line):
                hits.append(f"{f.relative_to(REPO)}:{n}: {line.strip()}")
            quoted += bool(_ENV_ITEM_LINE.match(line))
    assert quoted >= 24, quoted  # 9 loops + 15 fixed lines — the guard read the files it claims to
    assert not hits, hits


# render() $-escapes the secrets it hands to EVERY template as `env`; only compose output may read it.
_ENV_READ = re.compile(r"\benv\s*(?:\.|\[|\))|\bin\s+env\b")


def test_only_compose_templates_read_env() -> None:
    readers = sorted(
        str(f.relative_to(REPO))
        for f in TEMPLATES.rglob("*.j2")
        if f.name != "compose.yaml.j2"
        and f.name != "_companion_service.yaml.j2"
        and any(
            _ENV_READ.search(m)
            for m in re.findall(r"\{[{%].*?[}%]\}", f.read_text(encoding="utf-8"), re.S)
        )
    )
    assert not readers, readers


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
