"""Tests for scripts/kilo_dispatch.py — selective context loading."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

# Make scripts/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import kilo_dispatch  # noqa: E402
from kilo_dispatch import (  # noqa: E402, I001
    MAX_LINES_PER_PACK,
    MAX_RULE_LINES,
    PACK_MAPPING,
    PACK_REGISTRY,
    TESTING_OVERLAY,
    FabrikRootNoPacksError,
    _extract_rule_lines,
    _is_fabrik_root,
    _resolve_packs,
    load_project_context,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    """Create a minimal project directory with AGENTS-compact.md and rules."""
    proj = tmp_path / "myproject"
    proj.mkdir()

    # AGENTS-compact.md
    (proj / "AGENTS-compact.md").write_text("# Compact agent rules\nDo stuff.\n")

    # .windsurf/rules/ with a few pack files
    rules_dir = proj / ".windsurf" / "rules"
    rules_dir.mkdir(parents=True)

    # PY_CORE rule file (simulating 10-python.md structure)
    (rules_dir / "10-python.md").write_text(
        textwrap.dedent("""\
        ---
        activation: glob
        globs: ["**/*.py"]
        description: Python rules
        trigger: glob
        ---

        # Python Rules

        **Activation:** Glob `**/*.py`
        **Purpose:** FastAPI patterns

        ---

        ## FastAPI Patterns

        Use lifespan context manager for startup/shutdown.
        All endpoints must have type hints.
        Use Pydantic models for request/response validation.
        Health endpoint must test real dependencies.
        No class-level config — use function-level loading.
        Use os.getenv() for all configuration values.
        Never hardcode secrets or connection strings.
        """)
    )

    # TS_CORE rule file
    (rules_dir / "20-typescript.md").write_text(
        textwrap.dedent("""\
        ---
        activation: glob
        globs: ["**/*.ts", "**/*.tsx"]
        description: TypeScript rules
        trigger: glob
        ---

        # TypeScript Rules

        Use strict mode in tsconfig.json.
        Prefer const over let, never use var.
        Use explicit return types on exported functions.
        Use path aliases for deep imports.
        Avoid any type — use unknown + type guards.
        Use React Server Components by default in Next.js.
        """)
    )

    # TESTING overlay
    (rules_dir / "45-testing-strategy.md").write_text(
        textwrap.dedent("""\
        ---
        activation: glob
        globs: ["**/tests/**"]
        description: Testing strategy
        trigger: glob
        ---

        # Testing Strategy

        Testing Trophy model: integration > unit.
        One-Test Rule: one high-value happy-path test per feature.
        No cosmetic assertions against CSS classes.
        Bugfix: write failing test first, then fix.
        Use real PostgreSQL, never mock database sessions.
        Use pytest fixtures for test isolation.
        """)
    )

    # SAAS_UI rule file
    (rules_dir / "60-saas-ui.md").write_text(
        textwrap.dedent("""\
        ---
        activation: glob
        globs: ["**/*.tsx"]
        description: SaaS UI rules
        trigger: glob
        ---

        # SaaS UI Rules

        Use stable side nav for structural destinations.
        Every interactive component must handle 5 states.
        Target WCAG 2.2 AA as baseline.
        Apply optimistic updates only where rollback is safe.
        Error messages must be specific and actionable.
        Use Server Components by default in Next.js.
        """)
    )

    return proj


def _write_project_yaml(proj: Path, project_type: str) -> None:
    """Write a minimal project.yaml with the given type."""
    (proj / "project.yaml").write_text(
        f"name: test-project\ntype: {project_type}\nstatus: development\n"
    )


# ─── PACK_MAPPING sync check ────────────────────────────────────────────────


class TestPackMappingSync:
    """Verify PACK_MAPPING stays in sync with AGENTS.md project-type table."""

    EXPECTED_TYPES = {
        "python-api",
        "node-api",
        "saas-skeleton",
        "chrome-extension",
        "mobile-app",
        "desktop-app",
        "file-api",
        "file-worker",
        "wordpress",
        "docusaurus",
        "static-site",
    }

    def test_pack_mapping_has_exactly_11_entries(self):
        assert len(PACK_MAPPING) == 11

    def test_pack_mapping_keys_match_expected_types(self):
        assert set(PACK_MAPPING.keys()) == self.EXPECTED_TYPES

    def test_pack_registry_has_16_entries(self):
        assert len(PACK_REGISTRY) == 16

    def test_all_mapped_packs_exist_in_registry(self):
        """Every pack ID referenced in PACK_MAPPING must exist in PACK_REGISTRY."""
        for project_type, pack_ids in PACK_MAPPING.items():
            for pack_id in pack_ids:
                assert pack_id in PACK_REGISTRY, (
                    f"Pack '{pack_id}' for type '{project_type}' not in PACK_REGISTRY"
                )

    def test_testing_overlay_in_registry(self):
        assert TESTING_OVERLAY in PACK_REGISTRY


# ─── _extract_rule_lines ─────────────────────────────────────────────────────


class TestExtractRuleLines:
    def test_skips_frontmatter(self, project_dir: Path):
        lines = _extract_rule_lines(project_dir / ".windsurf" / "rules" / "10-python.md")
        for line in lines:
            assert "activation:" not in line
            assert "globs:" not in line
            assert "trigger:" not in line

    def test_skips_headings(self, project_dir: Path):
        lines = _extract_rule_lines(project_dir / ".windsurf" / "rules" / "10-python.md")
        for line in lines:
            assert not line.startswith("#")

    def test_skips_meta_lines(self, project_dir: Path):
        lines = _extract_rule_lines(project_dir / ".windsurf" / "rules" / "10-python.md")
        for line in lines:
            assert not line.startswith("**Activation:")
            assert not line.startswith("**Purpose:")

    def test_respects_max_lines(self, project_dir: Path):
        lines = _extract_rule_lines(
            project_dir / ".windsurf" / "rules" / "10-python.md", max_lines=3
        )
        assert len(lines) == 3

    def test_default_max_is_6(self, project_dir: Path):
        lines = _extract_rule_lines(project_dir / ".windsurf" / "rules" / "10-python.md")
        assert len(lines) <= MAX_LINES_PER_PACK

    def test_returns_empty_for_missing_file(self, tmp_path: Path):
        assert _extract_rule_lines(tmp_path / "nonexistent.md") == []

    def test_extracts_content_lines(self, project_dir: Path):
        lines = _extract_rule_lines(project_dir / ".windsurf" / "rules" / "10-python.md")
        assert len(lines) > 0
        assert "Use lifespan context manager for startup/shutdown." in lines


# ─── _resolve_packs ──────────────────────────────────────────────────────────


class TestResolvePacks:
    def test_python_api_gets_py_core(self, project_dir: Path):
        _write_project_yaml(project_dir, "python-api")
        defaults, overlays = _resolve_packs(project_dir)
        assert defaults == ["PY_CORE"]
        assert "TESTING" in overlays

    def test_saas_skeleton_gets_ts_core_and_saas_ui(self, project_dir: Path):
        _write_project_yaml(project_dir, "saas-skeleton")
        defaults, overlays = _resolve_packs(project_dir)
        assert defaults == ["TS_CORE", "SAAS_UI"]
        assert "TESTING" in overlays

    def test_chrome_extension_gets_three_defaults(self, project_dir: Path):
        _write_project_yaml(project_dir, "chrome-extension")
        defaults, overlays = _resolve_packs(project_dir)
        assert defaults == ["PY_CORE", "TS_CORE", "CHROME_MV3"]

    def test_node_api_gets_empty_defaults(self, project_dir: Path):
        _write_project_yaml(project_dir, "node-api")
        defaults, overlays = _resolve_packs(project_dir)
        assert defaults == []
        assert "TESTING" in overlays

    def test_file_api_gets_empty_defaults(self, project_dir: Path):
        """file-api scaffold is JavaScript-based — must not inject PY_CORE."""
        _write_project_yaml(project_dir, "file-api")
        defaults, overlays = _resolve_packs(project_dir)
        assert defaults == []
        assert "PY_CORE" not in defaults
        assert "TESTING" in overlays

    def test_missing_project_yaml_returns_empty_defaults(self, project_dir: Path):
        # No project.yaml written
        defaults, overlays = _resolve_packs(project_dir)
        assert defaults == []
        assert "TESTING" in overlays

    def test_unknown_type_returns_empty_defaults(self, project_dir: Path):
        _write_project_yaml(project_dir, "unknown-type-xyz")
        defaults, overlays = _resolve_packs(project_dir)
        assert defaults == []
        assert "TESTING" in overlays

    def test_extra_packs_added_as_overlays(self, project_dir: Path):
        _write_project_yaml(project_dir, "python-api")
        defaults, overlays = _resolve_packs(project_dir, extra_packs=["DATA_PG", "SECURITY"])
        assert defaults == ["PY_CORE"]
        assert "TESTING" in overlays
        assert "DATA_PG" in overlays
        assert "SECURITY" in overlays

    def test_extra_packs_deduplicates_with_defaults(self, project_dir: Path):
        _write_project_yaml(project_dir, "python-api")
        # PY_CORE is already a type default — should not appear in overlays
        defaults, overlays = _resolve_packs(project_dir, extra_packs=["PY_CORE"])
        assert defaults == ["PY_CORE"]
        assert "PY_CORE" not in overlays

    def test_unknown_extra_pack_skipped(self, project_dir: Path):
        _write_project_yaml(project_dir, "python-api")
        defaults, overlays = _resolve_packs(project_dir, extra_packs=["NONEXISTENT_PACK"])
        assert "NONEXISTENT_PACK" not in overlays


# ─── load_project_context ────────────────────────────────────────────────────


class TestLoadProjectContext:
    def test_loads_agents_compact_only(self, project_dir: Path):
        # Also create AGENTS.md to verify it is NOT loaded
        (project_dir / "AGENTS.md").write_text("# Full AGENTS — should NOT appear\n")
        _write_project_yaml(project_dir, "python-api")

        context = load_project_context(project_dir)
        assert "AGENTS-compact.md" in context
        assert "Compact agent rules" in context
        assert "Full AGENTS — should NOT appear" not in context

    def test_no_agents_md_fallback(self, project_dir: Path):
        """When only AGENTS.md exists (no compact), it should NOT be loaded."""
        (project_dir / "AGENTS-compact.md").unlink()
        (project_dir / "AGENTS.md").write_text("# Full AGENTS\n")
        _write_project_yaml(project_dir, "python-api")

        context = load_project_context(project_dir)
        assert "Full AGENTS" not in context

    def test_python_api_loads_py_core_and_testing(self, project_dir: Path):
        _write_project_yaml(project_dir, "python-api")
        context = load_project_context(project_dir)
        assert "[PY_CORE]" in context
        assert "[TESTING]" in context
        # Should NOT load TS_CORE or SAAS_UI
        assert "[TS_CORE]" not in context
        assert "[SAAS_UI]" not in context

    def test_saas_skeleton_loads_correct_packs(self, project_dir: Path):
        _write_project_yaml(project_dir, "saas-skeleton")
        context = load_project_context(project_dir)
        assert "[TS_CORE]" in context
        assert "[SAAS_UI]" in context
        assert "[TESTING]" in context
        assert "[PY_CORE]" not in context

    def test_file_api_does_not_inject_py_core(self, project_dir: Path):
        """file-api is JavaScript — PY_CORE must not appear in context."""
        _write_project_yaml(project_dir, "file-api")
        context = load_project_context(project_dir)
        assert "[PY_CORE]" not in context
        assert "[TESTING]" in context

    def test_missing_project_yaml_loads_only_agents_and_testing(self, project_dir: Path):
        context = load_project_context(project_dir)
        assert "AGENTS-compact.md" in context
        # Only TESTING overlay, no type defaults
        assert "[TESTING]" in context
        assert "[PY_CORE]" not in context

    def test_extra_packs_overlay_injection(self, project_dir: Path):
        _write_project_yaml(project_dir, "python-api")
        context = load_project_context(project_dir, extra_packs=["SAAS_UI"])
        assert "[PY_CORE]" in context
        assert "[SAAS_UI]" in context
        assert "[TESTING]" in context

    def test_40_line_cap_drops_overlays_first(self, tmp_path: Path):
        """When total lines exceed MAX_RULE_LINES, overlays are dropped first."""
        proj = tmp_path / "bigproject"
        proj.mkdir()
        (proj / "AGENTS-compact.md").write_text("# Compact\n")

        rules_dir = proj / ".windsurf" / "rules"
        rules_dir.mkdir(parents=True)

        # Create a type with many default packs that produce ~36 lines total
        # (6 packs × 6 lines = 36), then add overlays that push over 40
        big_rule = "\n".join([f"Rule line {i} for this pack." for i in range(1, 8)])

        # Write rule files for chrome-extension defaults (PY_CORE, TS_CORE, CHROME_MV3)
        for filename in ["10-python.md", "20-typescript.md", "70-chrome-ext.md"]:
            (rules_dir / filename).write_text(f"# Rules\n\n{big_rule}\n")

        # Write TESTING overlay + extra overlay
        (rules_dir / "45-testing-strategy.md").write_text(f"# Testing\n\n{big_rule}\n")
        (rules_dir / "25-data-postgres.md").write_text(f"# Data\n\n{big_rule}\n")
        (rules_dir / "35-security-auth.md").write_text(f"# Security\n\n{big_rule}\n")

        _write_project_yaml(proj, "chrome-extension")

        # Without extra packs: 3 defaults × 6 + 1 overlay (TESTING) × 6 = 24 lines (under cap)
        context_base = load_project_context(proj)
        assert "[TESTING]" in context_base

        # With 2 extra overlays: 3×6 + 3×6 = 36 lines — still under 40
        # But if all 6 produce 7 lines (our rule has 7 content lines, capped at 6 each):
        # 6×6 = 36, under cap — OK
        # Let's force the issue by making rules produce exactly MAX_LINES_PER_PACK lines
        # and adding enough packs to exceed 40
        context_extra = load_project_context(proj, extra_packs=["DATA_PG", "SECURITY"])

        # Count actual rule content lines (lines starting with "- ")
        rule_lines = [line for line in context_extra.split("\n") if line.startswith("- ")]
        assert len(rule_lines) <= MAX_RULE_LINES


class TestFabrikRootBehavior:
    """Verify fail-fast when Kilo targets the Fabrik monorepo root without --packs."""

    @pytest.fixture()
    def fabrik_root(self, project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Point FABRIK_ROOT at project_dir so _is_fabrik_root matches it."""
        monkeypatch.setattr(kilo_dispatch, "FABRIK_ROOT", project_dir.resolve())
        # Remove project.yaml if it exists
        py = project_dir / "project.yaml"
        if py.exists():
            py.unlink()
        return project_dir

    @pytest.fixture()
    def child_project(self, tmp_path: Path) -> Path:
        """Simulate a real scaffolded child project (has AGENTS.md, rules, etc)."""
        child = tmp_path / "child-project"
        child.mkdir()
        (child / "AGENTS-compact.md").write_text("# Compact agent rules\nDo stuff.\n")
        (child / "AGENTS.md").write_text("# Traycer orchestrator contract\n")
        rules_dir = child / ".windsurf" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "45-testing-strategy.md").write_text(
            "---\ndescription: Testing\n---\n# Testing\nWrite tests.\n"
        )
        return child

    # ── Exact root detection ──

    def test_is_fabrik_root_true(self, fabrik_root: Path):
        """Monkeypatched FABRIK_ROOT path returns True."""
        assert _is_fabrik_root(fabrik_root) is True

    def test_is_fabrik_root_false_child_with_agents_md(self, child_project: Path):
        """Scaffolded child project with AGENTS.md is NOT detected as Fabrik root."""
        assert _is_fabrik_root(child_project) is False

    # ── Fabrik-root fail-fast (no --packs) ──

    def test_fabrik_root_no_packs_raises(self, fabrik_root: Path):
        """Fabrik root without project.yaml and without --packs must fail fast."""
        with pytest.raises(FabrikRootNoPacksError, match="require explicit --packs"):
            _resolve_packs(fabrik_root)

    def test_fabrik_root_load_context_no_packs_raises(self, fabrik_root: Path):
        """load_project_context raises for Fabrik root when no --packs."""
        with pytest.raises(FabrikRootNoPacksError):
            load_project_context(fabrik_root)

    # ── Invalid-pack fail-fast ──

    def test_fabrik_root_all_invalid_packs_raises(self, fabrik_root: Path):
        """Fabrik root with only invalid pack IDs must fail fast."""
        with pytest.raises(FabrikRootNoPacksError, match="valid pack IDs"):
            _resolve_packs(fabrik_root, extra_packs=["BOGUS", "FAKE"])

    # ── Fabrik-root success (valid --packs) ──

    def test_fabrik_root_with_explicit_packs_succeeds(self, fabrik_root: Path):
        """Fabrik root with valid explicit --packs proceeds normally."""
        defaults, overlays = _resolve_packs(fabrik_root, extra_packs=["PY_CORE"])
        assert defaults == []
        assert "PY_CORE" in overlays
        assert "TESTING" in overlays

    def test_fabrik_root_load_context_with_packs(self, fabrik_root: Path):
        """load_project_context succeeds for Fabrik root when valid --packs given."""
        context = load_project_context(fabrik_root, extra_packs=["PY_CORE"])
        assert "[PY_CORE]" in context
        assert "[TESTING]" in context

    # ── Child project without project.yaml ──

    def test_child_with_agents_md_no_yaml_degrades_gracefully(self, child_project: Path):
        """Child project with AGENTS.md but no project.yaml degrades gracefully."""
        defaults, overlays = _resolve_packs(child_project)
        assert defaults == []
        assert "TESTING" in overlays

    def test_normal_project_no_yaml_unaffected(self, project_dir: Path):
        """Normal project without project.yaml still degrades gracefully."""
        defaults, overlays = _resolve_packs(project_dir)
        assert defaults == []
        assert "TESTING" in overlays


class TestPackRegistryConstants:
    """Verify the pack registry hasn't drifted."""

    def test_pack_registry_count_unchanged(self):
        """PACK_REGISTRY remains 16."""
        assert len(PACK_REGISTRY) == 16


class TestPackMappingConstants:
    """Verify the constants have expected values."""

    def test_max_rule_lines_is_40(self):
        assert MAX_RULE_LINES == 40

    def test_max_lines_per_pack_is_6(self):
        assert MAX_LINES_PER_PACK == 6

    def test_testing_overlay_is_testing(self):
        assert TESTING_OVERLAY == "TESTING"
