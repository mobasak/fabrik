"""Regression test for ``templates/<t>/defaults.yaml`` shape blocks.

For every scaffold template that emits a `shape:` block, build a
synthetic spec from the template default + a public domain, run
:func:`resolve_applicability`, and assert the expected registrar set.

The expected set is derived from the **purpose** of each template:

* ``python-api`` / ``node-api`` — public service backends → gatus, glitchtip,
  grafana on by default; everything else opt-in per spec.
* ``saas-skeleton`` — bundled DB + persistent data → postgres, backrest on top.
* ``next-tailwind`` / ``static-site`` / ``docusaurus`` — public web surfaces →
  gatus + grafana; ``static-site`` and ``docusaurus`` skip glitchtip
  (kind=static, no server runtime to throw exceptions).
* ``wordpress`` — like saas-skeleton plus kind=wordpress.
* ``file-api`` — service with persistent data (R2 receipts) → gatus, glitchtip,
  grafana, backrest.
* ``file-worker`` — internal worker → glitchtip, grafana, backrest only;
  no Gatus (not public), no DNS.
* ``chrome-extension`` / ``desktop-app`` / ``mobile-app`` — companion backend
  is a service (kind=service) so glitchtip fires; is_public is false by
  default so Gatus is opt-in (operator flips per project).

Locks two specific invariants discovered 2026-05-06:

* T1 — chrome/desktop/mobile defaults previously had ``kind: static`` which
  silently skipped GlitchTip on every backend they scaffold.
* T2 — ``next-tailwind`` defaults had no ``shape:`` block at all, so a
  Next.js site with a domain still had ``is_public=false`` (pydantic
  default) and Gatus skipped.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from fabrik.orchestrator.infrastructure import resolve_applicability

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"

# Registrars expected to RUN by default for each template, given a spec
# that supplies a domain (the only thing the spec author always sets).
# Anything not in the set must resolve to False.
EXPECTED: dict[str, set[str]] = {
    "python-api":       {"gatus", "glitchtip", "grafana"},
    "node-api":         {"gatus", "glitchtip", "grafana"},
    "saas-skeleton":    {"postgres", "gatus", "backrest", "glitchtip", "grafana"},
    "next-tailwind":    {"gatus", "glitchtip", "grafana"},
    "static-site":      {"gatus", "grafana"},  # kind=static → no glitchtip
    "docusaurus":       {"gatus", "grafana"},  # kind=static → no glitchtip
    "wordpress":        {"postgres", "gatus", "backrest", "glitchtip", "grafana"},
    "file-api":         {"gatus", "backrest", "glitchtip", "grafana"},
    "file-worker":      {"backrest", "glitchtip", "grafana"},  # not public → no gatus
    "chrome-extension": {"glitchtip", "grafana"},  # is_public=false → no gatus
    "desktop-app":      {"glitchtip", "grafana"},
    "mobile-app":       {"glitchtip", "grafana"},
}

ALL_REGISTRARS = {
    "postgres", "redis", "gatus", "backrest", "glitchtip",
    "grafana", "authelia", "meilisearch", "prometheus",
}


def _load_template_shape(template: str) -> dict:
    """Read templates/<t>/defaults.yaml and return its shape block (or {})."""
    path = TEMPLATES_DIR / template / "defaults.yaml"
    if not path.exists():
        pytest.skip(f"{path} does not exist")
    data = yaml.safe_load(path.read_text()) or {}
    return data.get("shape") or {}


@pytest.mark.parametrize("template,expected_runs", sorted(EXPECTED.items()))
def test_template_defaults_resolve_to_expected_registrars(
    template: str, expected_runs: set[str]
) -> None:
    shape = _load_template_shape(template)

    # Synthetic spec — domain set so domain-gated registrars (gatus,
    # authelia, prometheus) can fire if the shape allows.
    spec = {
        "name": f"test-{template}",
        "domain": f"test-{template}.vps1.ocoron.com",
        "shape": shape,
        "infra": {},
    }

    resolved = resolve_applicability(spec)
    actual_runs = {name for name, (run, _reason) in resolved.items() if run}

    assert actual_runs == expected_runs, (
        f"{template} template defaults produced unexpected registrar set.\n"
        f"  expected: {sorted(expected_runs)}\n"
        f"  actual:   {sorted(actual_runs)}\n"
        f"  shape:    {shape}\n"
        f"  reasons:  {[(n, r) for n, (run, r) in resolved.items()]}"
    )


def test_chrome_desktop_mobile_companion_backends_get_glitchtip() -> None:
    """T1 regression: chrome/desktop/mobile defaults must NOT use kind=static.

    They scaffold a real backend service (see compose.yaml.j2) which must
    be picked up by the GlitchTip registrar. kind=static would silently
    skip GlitchTip and ship a backend with no error tracking.
    """
    for template in ("chrome-extension", "desktop-app", "mobile-app"):
        shape = _load_template_shape(template)
        assert shape.get("kind") == "service", (
            f"{template} defaults.yaml must declare kind=service so the "
            f"scaffolded backend gets GlitchTip; got kind={shape.get('kind')!r}"
        )


def test_next_tailwind_has_explicit_shape_block() -> None:
    """T2 regression: next-tailwind must declare a shape block.

    Without it, pydantic defaults give kind=service+is_public=false, and
    Gatus silently skips a public Next.js site.
    """
    shape = _load_template_shape("next-tailwind")
    assert shape, "next-tailwind/defaults.yaml must declare a shape block"
    assert shape.get("is_public") is True, (
        "next-tailwind shape.is_public must be true so Gatus auto-registers"
    )
