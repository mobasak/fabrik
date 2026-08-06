"""Compose-and-Traefik invariants for every deployable scaffold type.

Born from the B16/B18/B19 hunt (CHANGELOG ``Coolify v4 git-deploy verifier
path`` entry, 2026-04-27): the scaffolded ``compose.yaml`` is the file that
Coolify clones and consumes when deploying a git-source project, so any
scaffold type that ``SPEC_ENABLED_TYPES`` flags as deployable MUST emit a
compose with:

1. A service whose name == project name (Coolify maps ``traefik.http.routers.<name>``
   labels by service name; a generic ``app:`` service breaks routing AND
   ``docker ps`` lookups).
2. Hardcoded port + Host(...) values in Traefik labels — Coolify's compose
   parser does not expand ``${VAR:-default}`` inside label strings (B18),
   so any unexpanded shell-fallback in a label is a deploy-time 404.
3. Network ``coolify`` declared external so the container joins the Traefik
   mesh.

``file-worker`` is the one exception: it has no HTTP surface and therefore
no Traefik labels — the test enforces that it still emits a compose.yaml
(so git-source deploy works) but skips the routing assertions.

This test was the gate for a follow-up sweep that closed the same bug in
``saas-skeleton``, ``chrome-extension``, ``node-api``, ``file-api`` and
``file-worker`` (B20/B21/B22).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from fabrik.scaffold import create_project

FABRIK_ROOT = Path("/opt/fabrik")
requires_fabrik_env = pytest.mark.skipif(
    not FABRIK_ROOT.exists() or os.getenv("CI") == "true",
    reason="Requires full fabrik environment at /opt/fabrik",
)

# Every type ``SPEC_ENABLED_TYPES`` (in ``spec_generator.py``) considers
# deployable. Kept literal here rather than imported so the test fails
# loudly if a new type is added there but not registered in this list.
DEPLOYABLE_TYPES_HTTP = [
    "python-api",
    "python-api-gpu",
    "saas-skeleton",
    "node-api",
    "file-api",
    "static-site",
    "docusaurus",
]
DEPLOYABLE_TYPES_WORKER = ["file-worker"]


_UNEXPANDED_VAR = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*(?::-[^}]*)?\}")


def _scaffold(tmp_path: Path, project_type: str) -> Path:
    """Scaffold a project with a deterministic name and return its path.

    ``generate_spec=False`` keeps the test hermetic — without it,
    ``create_project`` writes a spec into ``specs/services/`` of the
    real Fabrik checkout, leaking artifacts on every run.
    """
    name = f"compose-test-{project_type.replace('_', '-')}"
    create_project(
        name=name,
        project_type=project_type,
        description=f"Compose/Traefik invariant test for {project_type}",
        base=tmp_path,
        generate_spec=False,
    )
    return tmp_path / name


def _read_compose(project_dir: Path) -> str:
    compose = project_dir / "compose.yaml"
    assert compose.exists(), (
        f"compose.yaml is mandatory for git-source deployment but was not "
        f"emitted for {project_dir.name}. Coolify clones the repo and "
        f"reads ``/compose.yaml``; without it the deploy errors with "
        f"``compose-file not found``."
    )
    return compose.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Compose existence + service-name invariants                                 #
# --------------------------------------------------------------------------- #


@requires_fabrik_env
@pytest.mark.parametrize("project_type", DEPLOYABLE_TYPES_HTTP + DEPLOYABLE_TYPES_WORKER)
def test_compose_exists(tmp_path, project_type):
    """Every deployable type must emit a compose.yaml at the project root."""
    project_dir = _scaffold(tmp_path, project_type)
    _read_compose(project_dir)  # asserts existence with a helpful message


@requires_fabrik_env
@pytest.mark.parametrize("project_type", DEPLOYABLE_TYPES_HTTP + DEPLOYABLE_TYPES_WORKER)
def test_compose_service_name_matches_project(tmp_path, project_type):
    """The compose service name must equal the project name.

    Coolify maps Traefik labels and the docker container name from the
    compose service key. A generic ``app:`` service produces
    ``app-<uuid>-<ts>`` containers that break ``docker ps`` lookups and
    Traefik label aggregation (the original B11 cause).
    """
    project_dir = _scaffold(tmp_path, project_type)
    content = _read_compose(project_dir)

    # First-level service entries appear as ``  <name>:`` (2-space indent).
    services = re.findall(r"^ {2}([A-Za-z][A-Za-z0-9_-]*):\s*$", content, re.MULTILINE)
    assert services, f"compose.yaml for {project_type} declares no services"
    expected = project_dir.name
    assert expected in services, (
        f"compose.yaml for {project_type} should declare a service named "
        f"``{expected}`` (matches project name + Coolify routing); "
        f"found services: {services}"
    )


@requires_fabrik_env
@pytest.mark.parametrize("project_type", DEPLOYABLE_TYPES_HTTP + DEPLOYABLE_TYPES_WORKER)
def test_compose_joins_fabrik_network(tmp_path, project_type):
    """Container must join the external ``fabrik`` network for the Traefik mesh.

    (Renamed from ``coolify`` 2026-05-31; ``fabrik apply`` rejects a compose
    declaring ``coolify``.)
    """
    project_dir = _scaffold(tmp_path, project_type)
    content = _read_compose(project_dir)
    assert "fabrik" in content, (
        f"compose.yaml for {project_type} must reference the ``fabrik`` "
        f"network so Traefik can route to the container"
    )
    assert re.search(r"external:\s*true", content), (
        f"compose.yaml for {project_type} must declare ``fabrik`` as "
        f"``external: true`` (the shared network is created out-of-band)"
    )


# --------------------------------------------------------------------------- #
# Traefik-label invariants (HTTP-exposed types only)                          #
# --------------------------------------------------------------------------- #


@requires_fabrik_env
@pytest.mark.parametrize("project_type", DEPLOYABLE_TYPES_HTTP)
def test_traefik_labels_present(tmp_path, project_type):
    """HTTP scaffolds must emit Traefik enable + Host(...) + port labels."""
    project_dir = _scaffold(tmp_path, project_type)
    content = _read_compose(project_dir)

    assert "traefik.enable=true" in content, (
        f"{project_type} compose.yaml is missing ``traefik.enable=true`` "
        f"label — Traefik will not route to the container"
    )
    assert re.search(r"traefik\.http\.routers\.[\w-]+\.rule=Host\(", content), (
        f"{project_type} compose.yaml is missing a ``Host(`...`)`` rule on "
        f"its router — Traefik will 404 even on a healthy container "
        f"(see B16 in CHANGELOG)"
    )
    assert re.search(
        r"traefik\.http\.services\.[\w-]+\.loadbalancer\.server\.port=\d+",
        content,
    ), (
        f"{project_type} compose.yaml's loadbalancer.server.port label "
        f"must be a literal integer. ``${{PORT:-8000}}`` and similar "
        f"shell fallbacks are NOT expanded by Coolify's compose parser "
        f"and are passed verbatim to Traefik, which can't parse them "
        f"(see B18 in CHANGELOG)"
    )


@requires_fabrik_env
@pytest.mark.parametrize("project_type", DEPLOYABLE_TYPES_HTTP)
def test_traefik_labels_have_no_unexpanded_vars(tmp_path, project_type):
    """No Traefik label may contain an unexpanded ``${VAR}`` literal.

    Same root cause as B18: Coolify treats label strings as opaque, so
    ``${COMPOSE_PROJECT_NAME:-saas}`` becomes part of the router name
    and breaks routing.
    """
    project_dir = _scaffold(tmp_path, project_type)
    content = _read_compose(project_dir)

    offending: list[str] = []
    for line in content.splitlines():
        # Only inspect actual Traefik label lines.
        if "traefik." not in line:
            continue
        match = _UNEXPANDED_VAR.search(line)
        if match:
            offending.append(f"  {line.strip()!r}  (matched {match.group(0)!r})")

    assert not offending, (
        f"{project_type} compose.yaml has unexpanded shell variables "
        f"inside Traefik labels (Coolify will not expand them):\n" + "\n".join(offending)
    )


@requires_fabrik_env
@pytest.mark.parametrize("project_type", DEPLOYABLE_TYPES_HTTP)
def test_traefik_host_uses_real_domain(tmp_path, project_type):
    """The Host(...) rule must point at the project's real .vps1.ocoron.com FQDN.

    Templates that ship with placeholder hosts like ``localhost`` or
    ``${DOMAIN:-...}`` deploy successfully but Traefik routes them to
    the wrong vhost — Coolify's wildcard cert + DNS expects the real
    project domain.
    """
    project_dir = _scaffold(tmp_path, project_type)
    content = _read_compose(project_dir)

    host_match = re.search(
        r"traefik\.http\.routers\.[\w-]+\.rule=Host\(`([^`]+)`\)",
        content,
    )
    assert host_match, f"{project_type} compose.yaml has no parseable Host(`...`) rule"
    host = host_match.group(1)
    assert "${" not in host, (
        f"{project_type} compose.yaml Host(...) rule still contains an "
        f"unexpanded shell variable: {host!r}"
    )
    assert host == f"{project_dir.name}.vps1.ocoron.com", (
        f"{project_type} compose.yaml Host(...) should target "
        f"``{project_dir.name}.vps1.ocoron.com`` (default Fabrik domain "
        f"convention) but is {host!r}"
    )


# --------------------------------------------------------------------------- #
# Worker-specific invariants                                                  #
# --------------------------------------------------------------------------- #


@requires_fabrik_env
def test_worker_compose_has_no_traefik(tmp_path):
    """``file-worker`` has no HTTP surface — it must not emit Traefik labels.

    A worker behind Traefik with no listening port produces health-check
    spam and confuses status dashboards. The compose still exists (so
    git-source deploy works) but with no routing.
    """
    project_dir = _scaffold(tmp_path, "file-worker")
    content = _read_compose(project_dir)
    # Only inspect non-comment lines: the header doc block legitimately
    # mentions ``traefik`` while explaining the invariants.
    label_hits = [
        line
        for line in content.splitlines()
        if "traefik." in line and not line.lstrip().startswith("#")
    ]
    assert not label_hits, (
        "file-worker should not declare Traefik labels — it is a "
        "background worker with no HTTP surface. Offending lines:\n" + "\n".join(label_hits)
    )
