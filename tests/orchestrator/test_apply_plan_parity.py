"""fabrik apply resolves the same registrars as fabrik plan (W-989653a7, plan-2 Phase B).

Input domain: every spec in ``specs/services/`` (69 at 2026-10-17) and every ``templates/*/defaults.yaml``,
read from THIS checkout (``REPO`` is derived from the test file, so a worktree grades its own tree). Apply loads a
spec through ``SpecValidator.load_spec`` (the template's ``shape:`` block merged under the spec, D-908); plan loads it
through ``spec_loader.load_spec`` (every template key merged) and ``destroyer._spec_to_dict``. The registrar decision
reads only ``shape``, so the two must resolve the same registrars, reason strings included. A raise from either loader
is a FAILURE, never a skip. ``is_private_ip`` is stubbed in the validate-parity grader (it resolves DNS; the stub is
the one ``tests/orchestrator/test_validator.py`` uses), so the suite stays hermetic.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml

from fabrik import spec_loader
from fabrik.orchestrator.destroyer import _spec_to_dict
from fabrik.orchestrator.exceptions import ValidationError
from fabrik.orchestrator.infrastructure import resolve_applicability
from fabrik.orchestrator.validator import SpecValidator

REPO = Path(__file__).resolve().parents[2]
SPECS = sorted((REPO / "specs" / "services").glob("*.yaml"))
TEMPLATE_DEFAULTS = sorted((REPO / "templates").glob("*/defaults.yaml"))
assert SPECS, f"no specs under {REPO / 'specs' / 'services'}"
assert TEMPLATE_DEFAULTS, f"no template defaults under {REPO / 'templates'}"

# The nine shape keys templates set today; a new one is a decision, not a drive-by.
TEMPLATE_SHAPE_ALLOW = frozenset(
    {
        "exposes_metrics",
        "has_bearer_api",
        "has_persistent_data",
        "has_search_feature",
        "is_admin_dashboard",
        "is_public",
        "kind",
        "needs_cache",
        "needs_database",
    }
)

# The four live specs Phase A pinned (D-907): what apply runs for each today.
FROZEN_RUNNING = {
    "translator": {"glitchtip", "grafana", "postgres", "watchdog"},
    "longephedia-vault": {"gatus", "glitchtip", "grafana", "watchdog"},
    "fabrik-citation-verifier": {
        "backrest",
        "gatus",
        "glitchtip",
        "grafana",
        "postgres",
        "watchdog",
    },
    "fabrik-claim-validator": {"gatus", "glitchtip", "grafana", "postgres", "watchdog"},
}


def _validator() -> SpecValidator:
    return SpecValidator(templates_dir=REPO / "templates")


def _validate_outcome(spec: dict[str, Any]) -> str | None:
    """The error ``SpecValidator.validate`` raises on a copy of ``spec``, or None when it passes."""
    with patch("fabrik.orchestrator.validator.is_private_ip", return_value=False):
        try:
            _validator().validate(copy.deepcopy(spec))
        except ValidationError as e:
            return str(e)
    return None


def _validate_mismatch(raw: dict[str, Any]) -> str | None:
    """A report when validate's verdict on the raw spec differs from its verdict on the shape-merged one."""
    merged = spec_loader.merge_template_defaults(
        copy.deepcopy(raw), REPO / "templates", keys=("shape",)
    )
    before, after = _validate_outcome(raw), _validate_outcome(merged)
    return None if before == after else f"raw: {before!r} · shape-merged: {after!r}"


def _template_shape(template: Any) -> dict[str, Any]:
    if not (isinstance(template, str) and template):
        return {}
    path = REPO / "templates" / template / "defaults.yaml"
    if not path.is_file():
        return {}
    shape = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("shape")
    return shape if isinstance(shape, dict) else {}


def _kind_disagrees(raw: dict[str, Any]) -> str | None:
    """A report when the spec's top-level ``kind`` differs from its template's ``shape.kind`` and the spec sets no
    ``shape.kind`` of its own (the merged shape would carry the template's kind against the spec's word)."""
    top = raw.get("kind")
    own_shape = raw.get("shape")
    if top is None or (isinstance(own_shape, dict) and "kind" in own_shape):
        return None
    template_kind = _template_shape(raw.get("template")).get("kind")
    if template_kind is None or str(template_kind) == str(top):
        return None
    return (
        f"top-level kind {top!r} vs template {raw.get('template')!r} shape.kind {template_kind!r}"
    )


def _raw(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path.name} is not a mapping"
    return data


@pytest.mark.parametrize("path", SPECS, ids=lambda p: p.stem)
def test_apply_and_plan_resolve_the_same_registrars(path: Path) -> None:
    apply_view = resolve_applicability(_validator().load_spec(path))
    plan_view = resolve_applicability(_spec_to_dict(spec_loader.load_spec(path)))
    assert apply_view == plan_view


@pytest.mark.parametrize("path", SPECS, ids=lambda p: p.stem)
def test_validate_agrees_on_raw_and_shape_merged(path: Path) -> None:
    assert _validate_mismatch(_raw(path)) is None


@pytest.mark.parametrize("name", sorted(FROZEN_RUNNING))
def test_pinned_specs_run_their_frozen_registrars(name: str) -> None:
    spec = _validator().load_spec(REPO / "specs" / "services" / f"{name}.yaml")
    running = {
        reg for reg, (should_run, _reason) in resolve_applicability(spec).items() if should_run
    }
    assert running == FROZEN_RUNNING[name]


@pytest.mark.parametrize("path", SPECS, ids=lambda p: p.stem)
def test_spec_kind_agrees_with_its_template(path: Path) -> None:
    assert _kind_disagrees(_raw(path)) is None


@pytest.mark.parametrize("path", TEMPLATE_DEFAULTS, ids=lambda p: p.parent.name)
def test_template_shape_keys_stay_in_the_allow_list(path: Path) -> None:
    shape = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("shape") or {}
    assert isinstance(shape, dict)
    assert set(shape) <= TEMPLATE_SHAPE_ALLOW, set(shape) - TEMPLATE_SHAPE_ALLOW
    assert shape.get("is_admin_dashboard") is not True
    assert "uses_claude_cli" not in shape


# Positive controls for the two graders no live spec can redden (every live spec carries a domain or an explicit
# kind that agrees with its template's).
_SYNTH = {"name": "synth", "kind": "worker", "template": "python-api"}


def test_validate_mismatch_reports_a_divergent_verdict() -> None:
    report = _validate_mismatch(copy.deepcopy(_SYNTH))
    assert report is not None
    assert "raw: None" in report and "Missing required field: domain" in report


def test_kind_disagreement_is_reported() -> None:
    assert _kind_disagrees(copy.deepcopy(_SYNTH)) is not None
