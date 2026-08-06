"""Phase 4k acceptance tests — Shape model, per-type emission, deprecation warning.

These tests cover the two Plan acceptance criteria:
  * ``fabrik scaffold my-test --type python-api`` emits populated ``shape:``
    block matching the CLI Entry Points matrix row for ``python-api``;
    no ``infra:`` block.
  * ``fabrik new`` emits deprecation warning with pointer to ``fabrik scaffold``.

Plus:
  * ``Shape`` model enforces ``extra="forbid"`` so typos in ``defaults.yaml``
    fail loudly at scaffold/apply time, never silently.
  * ``Kind`` enum was widened with ``STATIC`` + ``WORDPRESS``.
  * Every scaffold type's ``templates/<type>/defaults.yaml`` has a ``shape:``
    block whose values round-trip through the pydantic ``Shape`` model.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from fabrik.scaffold import SCAFFOLD_TYPES
from fabrik.spec_generator import _build_shape_for_type, _load_template_defaults
from fabrik.spec_loader import Kind, Shape

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


# --- Shape pydantic model ---------------------------------------------------


class TestShapeModel:
    """The authoritative pydantic schema for ``shape:`` blocks."""

    def test_defaults_are_all_false_except_kind_service(self) -> None:
        """Absence of a shape block resolves to a plain HTTP service with no extras."""
        shape = Shape()
        assert shape.kind == Kind.SERVICE
        assert shape.is_public is False
        assert shape.is_admin_dashboard is False
        assert shape.has_bearer_api is False
        assert shape.has_persistent_data is False
        assert shape.needs_database is False
        assert shape.has_search_feature is False

    def test_extra_keys_are_forbidden(self) -> None:
        """Typos in defaults.yaml must fail loudly at load time."""
        with pytest.raises(ValidationError):
            # Intentional typo — real shape field is needs_database.
            Shape(need_database=True)  # type: ignore[call-arg]

    def test_kind_enum_widened_to_include_static_and_wordpress(self) -> None:
        """Phase 4k widened Kind so the orchestrator's hard-coded
        "wordpress" check has an enum-backed source of truth."""
        assert Kind.STATIC.value == "static"
        assert Kind.WORDPRESS.value == "wordpress"
        # Round-trip through YAML (defaults.yaml writes plain strings).
        shape = Shape(kind="wordpress")
        assert shape.kind is Kind.WORDPRESS

    def test_full_constructor_matches_saas_skeleton_row(self) -> None:
        """Sanity: a shape constructed with the saas-skeleton row values
        round-trips to exactly those values."""
        shape = Shape(
            kind="service",
            is_public=True,
            has_persistent_data=True,
            needs_database=True,
        )
        dumped = {k: (v.value if hasattr(v, "value") else v) for k, v in shape.model_dump().items()}
        assert dumped == {
            "kind": "service",
            "is_public": True,
            "is_admin_dashboard": False,
            "has_bearer_api": False,
            "has_persistent_data": True,
            "needs_database": True,
            "has_search_feature": False,
            "exposes_metrics": False,
            "needs_cache": False,
        }


# --- Per-type shape emission ------------------------------------------------


# (kind, is_public, is_admin, has_bearer, has_persistent, needs_db, has_search)
SHAPE_MATRIX: dict[str, tuple[str, bool, bool, bool, bool, bool, bool]] = {
    "python-api": ("service", True, False, False, False, False, False),
    "python-api-gpu": ("service", True, False, False, False, False, False),
    "node-api": ("service", True, False, False, False, False, False),
    "saas-skeleton": ("service", True, False, False, True, True, False),
    "file-api": ("service", True, False, False, True, False, False),
    "static-site": ("static", True, False, False, False, False, False),
    "docusaurus": ("static", True, False, False, False, False, False),
    "wordpress": ("wordpress", True, False, False, True, True, False),
    "file-worker": ("worker", False, False, False, True, False, False),
    # chrome/desktop/mobile companion backends are kind=service (T1 fix 2026-05-06)
    # so GlitchTip fires for the scaffolded backend (was wrongly kind=static).
    "chrome-extension": ("service", False, False, False, False, False, False),
    "mobile-app": ("service", False, False, False, False, False, False),
    "desktop-app": ("service", False, False, False, False, False, False),
}

# Recognised types with NO scaffold template of their own (creation lives
# elsewhere) → no defaults.yaml to assert. Still required in SHAPE_MATRIX so
# ``test_matrix_covers_every_scaffold_type`` stays in lockstep with
# SCAFFOLD_TYPES. ``wordpress`` scaffolding moved to /opt/wpf.
_NO_TEMPLATE_TYPES = {"wordpress"}


class TestDefaultsYamlShape:
    """Every scaffold type's defaults.yaml has a shape: block that matches the matrix."""

    def test_matrix_covers_every_scaffold_type(self) -> None:
        """If SCAFFOLD_TYPES grows, the matrix above must too. Fails fast."""
        assert set(SHAPE_MATRIX) == SCAFFOLD_TYPES, (
            f"SHAPE_MATRIX out of sync with SCAFFOLD_TYPES. "
            f"missing={SCAFFOLD_TYPES - set(SHAPE_MATRIX)} "
            f"extra={set(SHAPE_MATRIX) - SCAFFOLD_TYPES}"
        )

    @pytest.mark.parametrize("project_type", sorted(SHAPE_MATRIX))
    def test_defaults_yaml_has_shape_block(self, project_type: str) -> None:
        """Every type emits a shape: block via _build_shape_for_type."""
        if project_type in _NO_TEMPLATE_TYPES:
            pytest.skip(f"{project_type}: no scaffold template (deploy-only type)")
        shape = _build_shape_for_type(project_type)
        assert shape is not None, f"{project_type}: defaults.yaml missing shape: block"

    @pytest.mark.parametrize("project_type", sorted(SHAPE_MATRIX))
    def test_defaults_yaml_matches_matrix(self, project_type: str) -> None:
        """Every type's shape values match the plan's CLI Entry Points matrix exactly."""
        if project_type in _NO_TEMPLATE_TYPES:
            pytest.skip(f"{project_type}: no scaffold template (deploy-only type)")
        kind, is_pub, is_admin, has_bearer, has_pers, needs_db, has_search = SHAPE_MATRIX[
            project_type
        ]
        shape = _build_shape_for_type(project_type)
        assert shape is not None  # already asserted above, guard for type-checker
        assert shape.kind.value == kind
        assert shape.is_public is is_pub
        assert shape.is_admin_dashboard is is_admin
        assert shape.has_bearer_api is has_bearer
        assert shape.has_persistent_data is has_pers
        assert shape.needs_database is needs_db
        assert shape.has_search_feature is has_search

    @pytest.mark.parametrize("project_type", sorted(SHAPE_MATRIX))
    def test_defaults_yaml_parses_back_through_pydantic(self, project_type: str) -> None:
        """Idempotency: raw YAML dict parses cleanly into Shape — no lingering
        unknown keys that ``extra="forbid"`` would reject."""
        if project_type in _NO_TEMPLATE_TYPES:
            pytest.skip(f"{project_type}: no scaffold template (deploy-only type)")
        raw = _load_template_defaults(project_type).get("shape")
        assert raw is not None
        Shape(**raw)  # will raise if any key is invalid


# --- fabrik new deprecation -------------------------------------------------


class TestFabrikNewDeprecation:
    """`fabrik new` is hidden + warns. The second Plan acceptance criterion."""

    def test_new_hidden_from_help_listing(self) -> None:
        """`fabrik --help` lists `scaffold` but not `new`."""
        result = subprocess.run(
            [sys.executable, "-m", "fabrik.main", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Commands are indented with two spaces in click's help output.
        assert "  scaffold" in result.stdout, "scaffold should appear in --help"
        assert "  new " not in result.stdout, "new should be hidden from --help"

    def test_new_prints_deprecation_warning(self, tmp_path: Path) -> None:
        """Direct invocation still works but prints the deprecation warning to stderr.

        This is a smoke test against the installed ``fabrik`` CLI, which resolves
        back to this source tree (see earlier audit note that the CLI is editable-installed).
        Running against the actual entry point is the only way to verify ``hidden=True``
        + the ``click.echo(..., err=True)`` call together.
        """
        # Minimal invocation that reaches the deprecation echo: the warning fires
        # BEFORE template validation, so even a non-existent template shows it.
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "fabrik.main",
                "new",
                "deprec-smoke",
                "--template",
                "python-api",
                "--domain",
                "deprec.example.com",
                "--output",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Stderr should contain the DEPRECATED marker + pointer to scaffold.
        assert "DEPRECATED" in result.stderr, f"missing DEPRECATED in stderr: {result.stderr}"
        assert "fabrik scaffold" in result.stderr, (
            f"deprecation warning should point to `fabrik scaffold`: {result.stderr}"
        )


# --- spec_generator end-to-end -----------------------------------------------


class TestSpecGenerationEndToEnd:
    """The primary Plan acceptance criterion — shape: block in generated spec,
    no infra: block."""

    def test_python_api_generated_spec_has_expected_shape(self) -> None:
        """`fabrik scaffold --type python-api` emits a spec whose shape: block
        matches the python-api matrix row."""
        from fabrik.spec_generator import generate_spec

        spec = generate_spec(
            name="shape-test-api",
            project_type="python-api",
            domain="shape-test.example.com",
        )
        assert spec.shape is not None
        assert spec.shape.kind == Kind.SERVICE
        assert spec.shape.is_public is True
        assert spec.shape.needs_database is False

    def test_generated_spec_yaml_has_no_infra_block(self, tmp_path: Path) -> None:
        """Plan criterion: "no `infra:` block" in scaffolded specs.
        `infra:` is override-only and must not be pre-emptively emitted."""
        from fabrik.spec_generator import generate_spec
        from fabrik.spec_loader import save_spec

        spec = generate_spec(
            name="noinfra-test",
            project_type="python-api",
            domain="noinfra.example.com",
        )
        out = tmp_path / "noinfra.yaml"
        save_spec(spec, out)
        data = yaml.safe_load(out.read_text())
        assert "infra" not in data, (
            f"scaffolded spec must NOT have an `infra:` key; got keys={sorted(data)}"
        )
        # But shape: IS present with the expected kind.
        assert "shape" in data
        assert data["shape"]["kind"] == "service"
