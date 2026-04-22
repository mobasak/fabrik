"""Tests for ``scripts/enforcement/check_no_host_ports.py``.

Covers the Plan §5 acceptance criterion (line 2091):

    fails the lean gate if any ``templates/*/compose.yaml.j2`` contains a
    top-level ``ports:`` mapping (``"host:container"``) for services with
    a Traefik router.

Scope — what the check MUST flag:
  * Short-form ``"HOST:CONTAINER"`` (e.g. ``"8080:8080"``)
  * IP-prefixed ``"127.0.0.1:8080:8080"`` (DOCKER-USER doesn't filter loopback → still a risk)
  * Jinja-templated host bindings (``"{{ spec.port }}:8000"``) — the colon is the tell
  * Long-form ``published:`` key (that IS the host side of the binding)

Scope — what the check MUST NOT flag:
  * Container-only ports (``"8000"`` — no colon, no host-side binding)
  * Services without Traefik labels (non-routed containers may expose host ports
    — orthogonal policy, enforced by a different check)
  * The canonical shape (``labels:`` with ``traefik.enable=true`` and zero ``ports:``)

The rationale for the is-scoped-to-Traefik-routed-services rule is that
Traefik owns :80 / :443 via Coolify; a separately-exposed host port for the
same service would bypass middleware (Authelia, rate-limits, ACME) and defeat
the §10 admin-dashboard auth model. Non-Traefik containers (workers, one-shots)
don't have that concern.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "enforcement" / "check_no_host_ports.py"


# --- Import the script as a module so we can unit-test its functions. --------
# It lives under scripts/enforcement/ which is a package (has __init__.py), so
# we load it via importlib with an explicit spec to avoid polluting sys.path.


def _load_module():
    """Load the enforcement script as an importable module for unit tests."""
    spec = importlib.util.spec_from_file_location(
        "check_no_host_ports", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None, (
        f"cannot load {SCRIPT_PATH} — does the file exist?"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def check_module():
    return _load_module()


# --- Fixtures: synthetic compose.yaml.j2 content ---------------------------- #


CANONICAL_OK = textwrap.dedent(
    """\
    services:
      my-api:
        build: .
        platform: linux/amd64
        labels:
          - "traefik.enable=true"
          - "traefik.http.routers.my-api.rule=Host(`api.example.com`)"
          - "traefik.http.services.my-api.loadbalancer.server.port=8000"
        networks:
          - coolify
    """
)

NO_TRAEFIK_WITH_PORTS = textwrap.dedent(
    """\
    services:
      my-worker:
        build: .
        platform: linux/amd64
        ports:
          - "9999:9999"
        networks:
          - coolify
    """
)

CONTAINER_ONLY_PORT = textwrap.dedent(
    """\
    services:
      my-api:
        build: .
        labels:
          - "traefik.enable=true"
          - "traefik.http.routers.my-api.rule=Host(`api.example.com`)"
        ports:
          - "8000"
        networks:
          - coolify
    """
)

TRAEFIK_PLUS_SHORT_FORM_HOST_PORT = textwrap.dedent(
    """\
    services:
      my-api:
        build: .
        labels:
          - "traefik.enable=true"
          - "traefik.http.routers.my-api.rule=Host(`api.example.com`)"
        ports:
          - "8080:8080"
        networks:
          - coolify
    """
)

TRAEFIK_PLUS_IP_PREFIXED_HOST_PORT = textwrap.dedent(
    """\
    services:
      my-api:
        build: .
        labels:
          - "traefik.enable=true"
          - "traefik.http.routers.my-api.rule=Host(`api.example.com`)"
        ports:
          - "127.0.0.1:8080:8080"
        networks:
          - coolify
    """
)

TRAEFIK_PLUS_JINJA_TEMPLATED_HOST_PORT = textwrap.dedent(
    """\
    services:
      my-api:
        build: .
        labels:
          - "traefik.enable=true"
          - "traefik.http.routers.my-api.rule=Host(`{{ domain }}`)"
        ports:
          - "{{ spec.port }}:8000"
        networks:
          - coolify
    """
)

TRAEFIK_PLUS_LONG_FORM_PUBLISHED = textwrap.dedent(
    """\
    services:
      my-api:
        build: .
        labels:
          - "traefik.enable=true"
          - "traefik.http.routers.my-api.rule=Host(`api.example.com`)"
        ports:
          - target: 8000
            published: 8080
            protocol: tcp
        networks:
          - coolify
    """
)

TRAEFIK_INSIDE_JINJA_IF = textwrap.dedent(
    """\
    services:
      my-api:
        build: .
        {% if spec.expose.http %}
        labels:
          - "traefik.enable=true"
          - "traefik.http.routers.my-api.rule=Host(`{{ domain }}`)"
        {% endif %}
        ports:
          - "8080:8080"
        networks:
          - coolify
    """
)


# --- Unit tests: scan_template() ------------------------------------------- #


class TestScanTemplateNegatives:
    """Inputs that MUST produce zero violations."""

    def test_canonical_shape_emits_zero_violations(self, check_module, tmp_path: Path) -> None:
        f = tmp_path / "ok.yaml.j2"
        f.write_text(CANONICAL_OK)
        assert check_module.scan_template(f) == []

    def test_non_traefik_service_with_host_ports_is_not_flagged(
        self, check_module, tmp_path: Path
    ) -> None:
        """Services without Traefik labels are outside this check's scope.
        Publishing ports without Traefik routing is a different policy concern
        (likely just a worker or one-shot container)."""
        f = tmp_path / "worker.yaml.j2"
        f.write_text(NO_TRAEFIK_WITH_PORTS)
        assert check_module.scan_template(f) == []

    def test_container_only_port_on_traefik_service_is_not_flagged(
        self, check_module, tmp_path: Path
    ) -> None:
        """``"8000"`` (no colon) does NOT bind a host port — it's informational.
        Docker Compose treats it as an expose-style declaration."""
        f = tmp_path / "ok.yaml.j2"
        f.write_text(CONTAINER_ONLY_PORT)
        assert check_module.scan_template(f) == []


class TestScanTemplatePositives:
    """Inputs that MUST produce at least one violation."""

    @pytest.mark.parametrize(
        ("fixture_name", "fixture_text", "expected_substring"),
        [
            ("short_form", TRAEFIK_PLUS_SHORT_FORM_HOST_PORT, "8080:8080"),
            ("ip_prefixed", TRAEFIK_PLUS_IP_PREFIXED_HOST_PORT, "127.0.0.1:8080:8080"),
            ("jinja_templated", TRAEFIK_PLUS_JINJA_TEMPLATED_HOST_PORT, "{{ spec.port }}:8000"),
            ("long_form_published", TRAEFIK_PLUS_LONG_FORM_PUBLISHED, "published"),
            ("traefik_inside_jinja_if", TRAEFIK_INSIDE_JINJA_IF, "8080:8080"),
        ],
    )
    def test_host_binding_patterns_are_flagged(
        self, check_module, tmp_path: Path, fixture_name: str, fixture_text: str, expected_substring: str
    ) -> None:
        """Each of the five host-binding patterns must produce exactly one violation
        and the offending line text must be carried through to the report so the
        operator can jump straight to it."""
        f = tmp_path / f"{fixture_name}.yaml.j2"
        f.write_text(fixture_text)
        violations = check_module.scan_template(f)
        assert len(violations) == 1, (
            f"{fixture_name}: expected 1 violation, got {len(violations)}: {violations}"
        )
        (path, service, line_no, line_text) = violations[0]
        assert path == f
        assert service == "my-api"
        assert expected_substring in line_text, (
            f"{fixture_name}: line_text={line_text!r} missing substring {expected_substring!r}"
        )


# --- Integration: run the check against the real templates/ tree ----------- #


class TestAgainstRealTemplates:
    """Exercise the check against the 13 real ``templates/*/compose.yaml.j2``
    files. These were manually audited 2026-04-20 and are all compliant —
    the check's job here is to lock that state as a regression guard."""

    def test_every_real_template_is_compliant_today(self, check_module) -> None:
        templates_dir = REPO_ROOT / "templates"
        violations: list = []
        for path in templates_dir.rglob("compose.yaml.j2"):
            violations.extend(check_module.scan_template(path))
        assert violations == [], (
            "Real-template audit failed — a compose.yaml.j2 now has a "
            "Traefik router + host-bound port. Fix the template BEFORE "
            f"this check lands in the lean gate. Violations: {violations}"
        )

    def test_cli_exits_zero_on_clean_repo(self) -> None:
        """End-to-end: invoking the script as a subprocess exits 0 today."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=10,
        )
        assert result.returncode == 0, (
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )

    def test_cli_exits_nonzero_on_injected_violation(self, tmp_path: Path) -> None:
        """Copy the repo's python-api template into a tmpdir, inject a
        host port, point the script at that tmpdir, and confirm it exits 1
        with the offending file named in stdout. This is the regression-guard
        proof: if someone adds ``ports: ["8000:8000"]`` to a template, CI
        refuses to go green."""
        synthetic_templates = tmp_path / "templates" / "bad-template"
        synthetic_templates.mkdir(parents=True)
        compose = synthetic_templates / "compose.yaml.j2"
        compose.write_text(TRAEFIK_PLUS_SHORT_FORM_HOST_PORT)

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--templates-dir", str(tmp_path / "templates")],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=10,
        )
        assert result.returncode == 1, (
            f"expected exit 1, got {result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        assert "bad-template" in result.stdout or "bad-template" in result.stderr
        # Line-level detail must be in the report so operators can fix fast.
        assert "8080:8080" in result.stdout or "8080:8080" in result.stderr
