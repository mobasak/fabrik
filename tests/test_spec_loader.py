"""Tests for ``fabrik.spec_loader`` — T1-02 G-B1a template-defaults deep-merge.

The deep-merge step lets pre-G1 specs (which were written before scaffolds
emitted explicit ``shape:`` blocks) inherit the shape from their template's
``defaults.yaml`` at load time. Without it, the orchestrator's
``resolve_applicability`` sees ``shape=None`` and silently skips all 9
registrars on those deploys — the cascade-failure that motivates G-B1a.

These tests are TDD-style: written before the merge implementation lands,
expected to fail on the pre-merge codebase, expected to pass after Step 3
adds ``_deep_merge`` + the call site in ``load_spec``.

Reference: pack v3.2 §1a Acceptance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fabrik.spec_loader import _deep_merge, load_spec


# ──────────────────────────────────────────────────────────────────────────
# Fixtures: minimal specs written to a tmp dir + a sibling templates/ tree.
# The fixture builds a fully-isolated /tmp filesystem so tests don't depend
# on /opt/fabrik/specs/services state (which drifts) or on the real
# templates/ tree (which is itself the system-under-test for the registry).
# ──────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_fabrik_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a temp Fabrik-shaped tree and point FABRIK_ROOT at it."""
    (tmp_path / "templates" / "python-api").mkdir(parents=True)
    (tmp_path / "templates" / "file-worker").mkdir(parents=True)
    (tmp_path / "specs" / "services").mkdir(parents=True)

    (tmp_path / "templates" / "python-api" / "defaults.yaml").write_text(
        "shape:\n"
        "  kind: service\n"
        "  is_public: true\n"
        "  is_admin_dashboard: false\n"
        "  has_bearer_api: false\n"
        "  has_persistent_data: false\n"
        "  needs_database: false\n"
        "  has_search_feature: false\n"
        "  exposes_metrics: true\n"
        "env:\n"
        "  LOG_LEVEL: INFO\n"
    )
    (tmp_path / "templates" / "file-worker" / "defaults.yaml").write_text(
        "shape:\n"
        "  kind: worker\n"
        "  is_public: false\n"
        "  is_admin_dashboard: false\n"
        "  has_bearer_api: false\n"
        "  has_persistent_data: true\n"
        "  needs_database: false\n"
        "  has_search_feature: false\n"
    )

    # Point both the module constant AND any cached importers at the tmp tree.
    import fabrik.spec_loader as sl_mod

    monkeypatch.setattr(sl_mod, "FABRIK_ROOT", tmp_path)
    return tmp_path


def _write_spec(root: Path, name: str, body: str) -> Path:
    path = root / "specs" / "services" / f"{name}.yaml"
    path.write_text(body)
    return path


# ──────────────────────────────────────────────────────────────────────────
# Case 1 — happy path: captcha-style spec (no shape block) inherits from
# python-api/defaults.yaml at load time.
# ──────────────────────────────────────────────────────────────────────────


def test_load_spec_merges_template_defaults_happy_path(tmp_fabrik_root: Path) -> None:
    """A spec with template=python-api but no shape: block gets the full shape
    from templates/python-api/defaults.yaml after merge."""
    spec_path = _write_spec(
        tmp_fabrik_root,
        "captcha",
        "id: captcha\n"
        "kind: service\n"
        "template: python-api\n"
        "domain: captcha.vps1.ocoron.com\n"
        "source:\n"
        "  type: local\n",
    )
    spec = load_spec(spec_path)
    assert spec.shape is not None, "shape must be inherited from template after G-B1a merge"
    assert spec.shape.is_public is True
    assert spec.shape.exposes_metrics is True  # inherited from template
    assert spec.shape.has_persistent_data is False


# ──────────────────────────────────────────────────────────────────────────
# Case 2 — spec wins on conflict: top-level kind override survives merge.
# ──────────────────────────────────────────────────────────────────────────


def test_load_spec_spec_wins_on_conflict(tmp_fabrik_root: Path) -> None:
    """When the spec sets a key that the template's defaults also sets, the
    spec value wins. Verified via `kind:` — spec says worker, template (file-worker)
    also says worker but if we override to service in spec, spec wins."""
    spec_path = _write_spec(
        tmp_fabrik_root,
        "test-override",
        "id: test-override\n"
        "kind: service\n"  # spec sets service explicitly
        "template: file-worker\n"  # template defaults to kind=worker
        "domain: test-override.vps1.ocoron.com\n",
    )
    spec = load_spec(spec_path)
    # spec.kind (top level) wins
    assert spec.kind.value == "service"


# ──────────────────────────────────────────────────────────────────────────
# Case 3 — nested dict merge: spec overrides ONE shape flag, the rest inherit.
# ──────────────────────────────────────────────────────────────────────────


def test_load_spec_nested_shape_partial_override(tmp_fabrik_root: Path) -> None:
    """Spec sets only shape.has_persistent_data=true; the other 7 flags come
    from the template. This is the most subtle merge case — naive shallow
    merge would replace the entire shape dict with just {has_persistent_data}."""
    spec_path = _write_spec(
        tmp_fabrik_root,
        "test-partial",
        "id: test-partial\n"
        "kind: service\n"
        "template: python-api\n"
        "domain: test-partial.vps1.ocoron.com\n"
        "shape:\n"
        "  has_persistent_data: true\n",  # overrides ONE flag only
    )
    spec = load_spec(spec_path)
    assert spec.shape.has_persistent_data is True, "spec override on this flag must win"
    assert spec.shape.is_public is True, "other flags must inherit from template"
    assert spec.shape.exposes_metrics is True, "metrics flag must inherit from template"


# ──────────────────────────────────────────────────────────────────────────
# Case 4 — proxy-pattern: spec's infra.postgres=false override survives merge,
# resolve_applicability returns the postgres entry with reason containing
# "infra.postgres". Substring assertion per FINAL-REVISIONS §T1-02 Step 4.
# ──────────────────────────────────────────────────────────────────────────


def test_load_spec_infra_override_survives_merge_and_resolves(
    tmp_fabrik_root: Path,
) -> None:
    """A spec that needs_database=true but explicitly sets infra.postgres=false
    must keep the override after merge; resolve_applicability then returns
    postgres as (False, reason-containing-'infra.postgres')."""
    from fabrik.orchestrator.infrastructure import resolve_applicability

    spec_path = _write_spec(
        tmp_fabrik_root,
        "test-proxy-override",
        "id: test-proxy-override\n"
        "kind: service\n"
        "template: python-api\n"
        "domain: test-proxy-override.vps1.ocoron.com\n"
        "shape:\n"
        "  needs_database: true\n"
        # `infra:` (NOT `infrastructure:`) is the free-form override block —
        # see Spec model's `infra:` field at spec_loader.py:381+ and
        # production proxy.yaml lines 42-43. `infrastructure:` is the
        # structured database/storage/auth config (different field).
        "infra:\n"
        "  postgres: false\n",
    )
    spec = load_spec(spec_path)
    spec_dict = spec.model_dump(mode="python")
    resolved = resolve_applicability(spec_dict)
    assert resolved["postgres"][0] is False, "postgres must NOT run due to infra override"
    assert "infra.postgres" in resolved["postgres"][1], (
        f"reason must mention infra.postgres override; got: {resolved['postgres'][1]!r}"
    )


# ──────────────────────────────────────────────────────────────────────────
# Case 5 — missing template tolerance: spec references a non-existent template
# defaults.yaml; load_spec should NOT crash. Shape stays None; the Spec model's
# downstream consumers handle None gracefully.
# ──────────────────────────────────────────────────────────────────────────


def test_load_spec_tolerates_missing_template_defaults(tmp_fabrik_root: Path) -> None:
    """If templates/<template>/defaults.yaml doesn't exist (typo, deleted
    template), load_spec should still load the raw spec — no crash."""
    spec_path = _write_spec(
        tmp_fabrik_root,
        "test-missing",
        "id: test-missing\n"
        "kind: service\n"
        "template: nonexistent-template\n"
        "domain: test-missing.vps1.ocoron.com\n",
    )
    # Must NOT raise:
    spec = load_spec(spec_path)
    assert spec.id == "test-missing"
    # shape stays None (no defaults to merge in)
    assert spec.shape is None


# ──────────────────────────────────────────────────────────────────────────
# Case 6 — empty/None overlay behavior: _deep_merge must handle the edge cases
# where overlay is empty dict, None, or has empty nested dicts without errors.
# ──────────────────────────────────────────────────────────────────────────


def test_deep_merge_edge_cases() -> None:
    """Unit-test _deep_merge directly for edge cases."""
    # Empty overlay → base wins
    assert _deep_merge({"a": 1, "b": {"c": 2}}, {}) == {"a": 1, "b": {"c": 2}}
    # Empty base → overlay wins
    assert _deep_merge({}, {"a": 1}) == {"a": 1}
    # Nested empty dict in overlay must NOT erase base nested dict
    assert _deep_merge({"a": {"x": 1}}, {"a": {}}) == {"a": {"x": 1}}
    # Overlay value of a different type than base wins (no recursive type-merge)
    assert _deep_merge({"a": {"x": 1}}, {"a": "scalar"}) == {"a": "scalar"}
    # Both empty
    assert _deep_merge({}, {}) == {}


# ──────────────────────────────────────────────────────────────────────────
# Case 7 — primary path integration: shape-less spec → load_spec →
# resolve_applicability returns the expected 4-registrar set for a public
# Python API with metrics. Verifies the full G-B1a cascade end-to-end.
# ──────────────────────────────────────────────────────────────────────────


def test_post_merge_resolves_full_registrar_set(tmp_fabrik_root: Path) -> None:
    """[PRIMARY PATH] (derived from Epic Brief SC-1): integration test for
    load_spec → resolve_applicability chain on a shape-less captcha-like spec.
    Expected registrars: gatus (is_public=true + domain), glitchtip
    (kind=service), grafana (always for shape.kind!=static), prometheus
    (exposes_metrics=true + domain set)."""
    from fabrik.orchestrator.infrastructure import resolve_applicability

    spec_path = _write_spec(
        tmp_fabrik_root,
        "captcha-style",
        "id: captcha-style\n"
        "kind: service\n"
        "template: python-api\n"  # template's defaults.yaml has exposes_metrics=true
        "domain: captcha-style.vps1.ocoron.com\n"
        "source:\n"
        "  type: local\n",
    )
    spec = load_spec(spec_path)
    assert spec.shape is not None
    resolved = resolve_applicability(spec.model_dump(mode="python"))
    runs = {name for name, (run, _reason) in resolved.items() if run}
    # python-api defaults: is_public=true, exposes_metrics=true, kind=service
    # → expect gatus, glitchtip, grafana, prometheus
    assert runs == {"gatus", "glitchtip", "grafana", "prometheus"}, (
        f"expected python-api shape-less spec to resolve to "
        f"{{gatus, glitchtip, grafana, prometheus}}; got {runs}"
    )
