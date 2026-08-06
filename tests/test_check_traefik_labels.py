"""Tests for ``scripts/enforcement/check_traefik_labels.py``.

Covers Plan §7 + the acceptance criterion at
``docs/development/plans/2026-04-18-zero-touch-deployment.md:2086``:

    Every emitted ``templates/*/compose.yaml.j2`` declares the full Traefik
    label set explicitly; no reliance on Coolify auto-inject (§7).

The "full Traefik label set" per §7 is the five labels below. Any service
opting into Traefik (``traefik.enable=true``) MUST declare all five —
missing even one invites the GlitchTip-class silent failure where Coolify's
auto-inject was masking the gap until a ``PATCH`` erased it:

    1. traefik.http.routers.<R>.rule=...
    2. traefik.http.routers.<R>.entrypoints=...
    3. traefik.http.routers.<R>.tls=true          ← commonly forgotten
    4. traefik.http.routers.<R>.tls.certresolver=...
    5. traefik.http.services.<S>.loadbalancer.server.port=...

The check is per-SERVICE, not per-router: a wordpress-style multi-router
template (apex + www-redirect + xmlrpc-block) passes as long as each of
the five label patterns appears at least once inside the service's
labels block. Router-name consistency is not policed here — traefik
resolves services implicitly by name match, and policing that would
require rendering the jinja (which we refuse to do; see
``check_no_host_ports.py`` module docstring for rationale).

Scope — what must be flagged:
  * Service with ``traefik.enable=true`` but missing ``tls=true``
  * Service with ``traefik.enable=true`` but missing any other required label
  * Service where ``.rule=`` is fine but ``.entrypoints=`` is absent

Scope — what must NOT be flagged:
  * Service without ``traefik.enable=true`` (out of scope — not routed)
  * Service with full five-label set (canonical shape)
  * ``traefik.enable=false`` — explicit opt-out, any other labels ignored
  * ``file-worker``-style templates that have no ``labels:`` block at all
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "enforcement" / "check_traefik_labels.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_traefik_labels", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None, f"cannot load {SCRIPT_PATH}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def check_module():
    return _load_module()


# --- Fixtures: synthetic compose.yaml.j2 content --------------------------- #

CANONICAL_FIVE_LABELS = textwrap.dedent(
    """\
    services:
      my-api:
        build: .
        labels:
          - "traefik.enable=true"
          - "traefik.http.routers.my-api.rule=Host(`api.example.com`)"
          - "traefik.http.routers.my-api.entrypoints=websecure"
          - "traefik.http.routers.my-api.tls=true"
          - "traefik.http.routers.my-api.tls.certresolver=letsencrypt"
          - "traefik.http.services.my-api.loadbalancer.server.port=8000"
    """
)

MISSING_TLS_TRUE = textwrap.dedent(
    """\
    services:
      my-api:
        labels:
          - "traefik.enable=true"
          - "traefik.http.routers.my-api.rule=Host(`api.example.com`)"
          - "traefik.http.routers.my-api.entrypoints=websecure"
          - "traefik.http.routers.my-api.tls.certresolver=letsencrypt"
          - "traefik.http.services.my-api.loadbalancer.server.port=8000"
    """
)

MISSING_ENTRYPOINTS = textwrap.dedent(
    """\
    services:
      my-api:
        labels:
          - "traefik.enable=true"
          - "traefik.http.routers.my-api.rule=Host(`api.example.com`)"
          - "traefik.http.routers.my-api.tls=true"
          - "traefik.http.routers.my-api.tls.certresolver=letsencrypt"
          - "traefik.http.services.my-api.loadbalancer.server.port=8000"
    """
)

MISSING_LOADBALANCER_PORT = textwrap.dedent(
    """\
    services:
      my-api:
        labels:
          - "traefik.enable=true"
          - "traefik.http.routers.my-api.rule=Host(`api.example.com`)"
          - "traefik.http.routers.my-api.entrypoints=websecure"
          - "traefik.http.routers.my-api.tls=true"
          - "traefik.http.routers.my-api.tls.certresolver=letsencrypt"
    """
)

NO_TRAEFIK_ENABLE = textwrap.dedent(
    """\
    services:
      my-worker:
        build: .
        networks:
          - coolify
    """
)

EXPLICIT_TRAEFIK_DISABLED = textwrap.dedent(
    """\
    services:
      internal:
        labels:
          - "traefik.enable=false"
          - "some.other.label=whatever"
    """
)

WORDPRESS_STYLE_MULTIPLE_ROUTERS = textwrap.dedent(
    """\
    services:
      wordpress:
        labels:
          - "traefik.enable=true"
          - "traefik.http.routers.wp.rule=Host(`site.example.com`)"
          - "traefik.http.routers.wp.entrypoints=websecure"
          - "traefik.http.routers.wp.tls=true"
          - "traefik.http.routers.wp.tls.certresolver=letsencrypt"
          - "traefik.http.routers.wp-www.rule=Host(`www.site.example.com`)"
          - "traefik.http.routers.wp-www.entrypoints=websecure"
          - "traefik.http.routers.wp-www.tls=true"
          - "traefik.http.routers.wp-www.tls.certresolver=letsencrypt"
          - "traefik.http.services.wp.loadbalancer.server.port=80"
    """
)

JINJA_TEMPLATED_NAMES = textwrap.dedent(
    """\
    services:
      my-api:
        labels:
          - "traefik.enable=true"
          - "traefik.http.routers.{{ spec.id }}.rule=Host(`{{ domain }}`)"
          - "traefik.http.routers.{{ spec.id }}.entrypoints=websecure"
          - "traefik.http.routers.{{ spec.id }}.tls=true"
          - "traefik.http.routers.{{ spec.id }}.tls.certresolver=letsencrypt"
          - "traefik.http.services.{{ spec.id }}.loadbalancer.server.port={{ spec.port }}"
    """
)

MULTI_SERVICE_ONE_BAD = textwrap.dedent(
    """\
    services:
      api:
        labels:
          - "traefik.enable=true"
          - "traefik.http.routers.api.rule=Host(`api.example.com`)"
          - "traefik.http.routers.api.entrypoints=websecure"
          - "traefik.http.routers.api.tls=true"
          - "traefik.http.routers.api.tls.certresolver=letsencrypt"
          - "traefik.http.services.api.loadbalancer.server.port=8000"
      frontend:
        labels:
          - "traefik.enable=true"
          - "traefik.http.routers.front.rule=Host(`example.com`)"
          - "traefik.http.routers.front.entrypoints=websecure"
          - "traefik.http.routers.front.tls.certresolver=letsencrypt"
          - "traefik.http.services.front.loadbalancer.server.port=3000"
    """
)


# --- Unit tests: scan_template() ------------------------------------------- #


class TestScanTemplateNegatives:
    """Inputs that MUST produce zero violations."""

    def test_canonical_five_labels_passes(self, check_module, tmp_path: Path) -> None:
        f = tmp_path / "ok.yaml.j2"
        f.write_text(CANONICAL_FIVE_LABELS)
        assert check_module.scan_template(f) == []

    def test_service_without_traefik_enable_is_not_flagged(
        self, check_module, tmp_path: Path
    ) -> None:
        """Non-routed services (workers, one-shots) are out of scope.
        Forcing Traefik labels on them would be architecturally wrong."""
        f = tmp_path / "worker.yaml.j2"
        f.write_text(NO_TRAEFIK_ENABLE)
        assert check_module.scan_template(f) == []

    def test_explicit_traefik_disabled_is_not_flagged(self, check_module, tmp_path: Path) -> None:
        """``traefik.enable=false`` is an explicit opt-out (some internal
        services keep labels around for documentation / tooling). The
        check must respect the opt-out and not require the rest of the set."""
        f = tmp_path / "internal.yaml.j2"
        f.write_text(EXPLICIT_TRAEFIK_DISABLED)
        assert check_module.scan_template(f) == []

    def test_multi_router_wordpress_style_passes(self, check_module, tmp_path: Path) -> None:
        f = tmp_path / "wp.yaml.j2"
        f.write_text(WORDPRESS_STYLE_MULTIPLE_ROUTERS)
        assert check_module.scan_template(f) == []

    def test_jinja_templated_router_names_pass(self, check_module, tmp_path: Path) -> None:
        """Opaque jinja tokens (``{{ spec.id }}``) count as valid router-
        name stand-ins; the check must be insensitive to the exact name."""
        f = tmp_path / "jinja.yaml.j2"
        f.write_text(JINJA_TEMPLATED_NAMES)
        assert check_module.scan_template(f) == []


class TestScanTemplatePositives:
    """Inputs that MUST produce at least one violation, naming the missing label."""

    @pytest.mark.parametrize(
        ("fixture_name", "fixture_text", "missing_label_marker"),
        [
            ("tls_true", MISSING_TLS_TRUE, "tls=true"),
            ("entrypoints", MISSING_ENTRYPOINTS, "entrypoints"),
            ("loadbalancer_port", MISSING_LOADBALANCER_PORT, "loadbalancer.server.port"),
        ],
    )
    def test_missing_required_label_is_flagged(
        self,
        check_module,
        tmp_path: Path,
        fixture_name: str,
        fixture_text: str,
        missing_label_marker: str,
    ) -> None:
        """Each fixture drops exactly one label. The violation report
        must name the missing label so an operator can fix fast."""
        f = tmp_path / f"{fixture_name}.yaml.j2"
        f.write_text(fixture_text)
        violations = check_module.scan_template(f)
        assert len(violations) == 1, (
            f"{fixture_name}: expected 1 violation, got {len(violations)}: {violations}"
        )
        (path, service, missing) = violations[0]
        assert path == f
        assert service == "my-api"
        assert any(missing_label_marker in m for m in missing), (
            f"{fixture_name}: missing labels list {missing!r} does not mention {missing_label_marker!r}"
        )

    def test_only_bad_service_flagged_in_multi_service_file(
        self, check_module, tmp_path: Path
    ) -> None:
        """File with two services — only the second is missing ``tls=true``.
        Must flag exactly that service, not the first."""
        f = tmp_path / "multi.yaml.j2"
        f.write_text(MULTI_SERVICE_ONE_BAD)
        violations = check_module.scan_template(f)
        assert len(violations) == 1
        (_, service, missing) = violations[0]
        assert service == "frontend"
        assert any("tls=true" in m for m in missing)


# --- Integration: run the check against the real templates/ tree ----------- #


class TestAgainstRealTemplates:
    """After the Track 2 template fix-up, every real ``compose.yaml.j2``
    must declare the full five-label set for every Traefik-enabled service.
    This is the regression guard — if a future PR drops a label, CI
    refuses to go green."""

    def test_every_real_template_is_compliant(self, check_module) -> None:
        templates_dir = REPO_ROOT / "templates"
        violations: list = []
        for path in templates_dir.rglob("compose.yaml.j2"):
            violations.extend(check_module.scan_template(path))
        assert violations == [], (
            "Traefik-label audit failed — a template now has a Traefik-"
            "enabled service missing one or more of the five required "
            f"labels per Plan §7. Violations: {violations}"
        )

    def test_cli_exits_zero_on_clean_repo(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=10,
        )
        assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"

    def test_cli_exits_nonzero_on_injected_violation(self, tmp_path: Path) -> None:
        synthetic = tmp_path / "templates" / "bad-template"
        synthetic.mkdir(parents=True)
        (synthetic / "compose.yaml.j2").write_text(MISSING_TLS_TRUE)

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--templates-dir",
                str(tmp_path / "templates"),
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=10,
        )
        assert result.returncode == 1, (
            f"expected 1, got {result.returncode}\n{result.stdout}\n{result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert "bad-template" in combined
        assert "tls=true" in combined, (
            "report must name the specific missing label so operators fix fast"
        )


class TestSkipWhenTemplatesDirAbsent:
    """Phase 2 (deploy-readiness-gaps): no ``templates/`` dir → skip with exit 0,
    not the old exit 2 that red-gated every non-fabrik project this script syncs to.
    final_gate's run_optional_check fails on any non-zero exit."""

    def test_cli_skips_with_exit_zero_when_templates_dir_missing(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--templates-dir", str(tmp_path / "nope")],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=10,
        )
        assert result.returncode == 0, (
            f"missing templates/ must skip with exit 0 (was exit 2). "
            f"got {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
        assert "[skip]" in result.stdout

    def test_cli_exits_zero_when_templates_dir_empty(self, tmp_path: Path) -> None:
        (tmp_path / "templates").mkdir()
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--templates-dir", str(tmp_path / "templates")],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=10,
        )
        assert result.returncode == 0, (
            f"empty templates/ must exit 0\nstdout={result.stdout}\nstderr={result.stderr}"
        )
