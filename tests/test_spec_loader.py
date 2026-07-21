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


# ──────────────────────────────────────────────────────────────────────────
# WatchdogConfig — T-P2 artifact 1
#
# Pins the contract from
# `docs/development/plans/2026-05-30-ai-watchdog-platform-P2-subplan.md` § 1
# so future refactors can't silently drift the defaults or weaken the
# at-least-one-cap validator (the defense against accidentally-uncapped
# projects). The validator is the only behavior in this artifact — every
# other field is a typed default; tests assert exact defaults so a typo
# in a future PR surfaces here, not in production cost-budget enforcement.
# ──────────────────────────────────────────────────────────────────────────


class TestWatchdogConfig:
    """T-P2 artifact 1 contract — WatchdogConfig + Spec.watchdog field."""

    def test_default_values_match_subplan(self) -> None:
        """All 10 field defaults match the P2 sub-plan § 1 verbatim."""
        from fabrik.spec_loader import WatchdogConfig

        w = WatchdogConfig()
        assert w.enabled is False
        assert w.daily_budget_usd == 1.0
        assert w.daily_invocations_cap == 200
        assert w.auto_tier_b is False
        assert w.escalation_channel == "apprise"
        assert w.llm_provider_primary == "claude-code"
        assert w.llm_provider_fallback == "openrouter"
        assert w.cheap_model == "haiku"
        assert w.expensive_model == "sonnet"
        assert w.per_incident_budget_usd == 0.50

    def test_extra_keys_forbidden(self) -> None:
        """``model_config = {"extra": "forbid"}`` — typos in spec YAML fail loud."""
        from pydantic import ValidationError

        from fabrik.spec_loader import WatchdogConfig

        with pytest.raises(ValidationError):
            WatchdogConfig(unknown_field="foo")  # type: ignore[call-arg]

    def test_literal_rejects_unknown_provider(self) -> None:
        """``llm_provider_primary`` is ``Literal["claude-code","openrouter"]``."""
        from pydantic import ValidationError

        from fabrik.spec_loader import WatchdogConfig

        with pytest.raises(ValidationError):
            WatchdogConfig(llm_provider_primary="gpt-4")  # type: ignore[arg-type]

    def test_caps_validator_blocks_uncapped_enabled(self) -> None:
        """When ``enabled=True``, at least one cap must be > 0.

        Defense against accidentally-uncapped projects — without this
        check, a typo or copy-paste error could land a watchdog with
        zero budget enforcement.
        """
        from pydantic import ValidationError

        from fabrik.spec_loader import WatchdogConfig

        with pytest.raises(ValidationError, match="requires at least one of"):
            WatchdogConfig(enabled=True, daily_budget_usd=0.0, daily_invocations_cap=0)

    def test_caps_validator_passes_with_usd_cap_only(self) -> None:
        """USD cap > 0 alone satisfies the at-least-one-cap rule."""
        from fabrik.spec_loader import WatchdogConfig

        w = WatchdogConfig(enabled=True, daily_budget_usd=1.0, daily_invocations_cap=0)
        assert w.enabled is True

    def test_caps_validator_passes_with_count_cap_only(self) -> None:
        """Invocation cap > 0 alone satisfies the at-least-one-cap rule."""
        from fabrik.spec_loader import WatchdogConfig

        w = WatchdogConfig(enabled=True, daily_budget_usd=0.0, daily_invocations_cap=50)
        assert w.enabled is True

    def test_caps_validator_skipped_when_disabled(self) -> None:
        """``enabled=False`` skips the cap check — disabled watchdogs cost nothing."""
        from fabrik.spec_loader import WatchdogConfig

        w = WatchdogConfig(enabled=False, daily_budget_usd=0.0, daily_invocations_cap=0)
        assert w.enabled is False

    # ── Tier-D (auto_code_fix) — Phase C ──────────────────────────────────

    def test_tier_d_defaults_off(self) -> None:
        """Tier-D ships off by default; window/critical_paths have safe defaults."""
        from fabrik.spec_loader import WatchdogConfig

        w = WatchdogConfig()
        assert w.auto_code_fix is False
        assert w.code_fix_window_sec == 1800  # 30-min human-review window (was 300 — too short)
        assert w.critical_paths == []

    def test_auto_code_fix_requires_propose_fix_prs(self) -> None:
        """Tier-D reuses the proposed-fix workspace clone, so it can't run
        without propose_fix_prs (agent.propose_fix returns None otherwise)."""
        from pydantic import ValidationError

        from fabrik.spec_loader import WatchdogConfig

        with pytest.raises(ValidationError, match="requires propose_fix_prs=true"):
            WatchdogConfig(
                enabled=True, daily_invocations_cap=50, auto_code_fix=True, propose_fix_prs=False
            )

    def test_auto_code_fix_ok_with_propose_fix_prs(self) -> None:
        from fabrik.spec_loader import WatchdogConfig

        w = WatchdogConfig(
            enabled=True, daily_invocations_cap=50, auto_code_fix=True, propose_fix_prs=True
        )
        assert w.auto_code_fix is True

    def test_code_fix_window_bounds(self) -> None:
        """Window is bounded 60..3600 (alert-storm floor / operator-sanity ceiling)."""
        from pydantic import ValidationError

        from fabrik.spec_loader import WatchdogConfig

        with pytest.raises(ValidationError):
            WatchdogConfig(code_fix_window_sec=30)
        with pytest.raises(ValidationError):
            WatchdogConfig(code_fix_window_sec=4000)

    def test_trigger_sources_default_empty(self) -> None:
        from fabrik.spec_loader import WatchdogConfig

        assert WatchdogConfig().trigger_sources == []

    def test_trigger_sources_accepts_known_tokens(self) -> None:
        from fabrik.spec_loader import WatchdogConfig

        w = WatchdogConfig(trigger_sources=["emitter", "health", "error_webhook"])
        assert "error_webhook" in w.trigger_sources

    def test_trigger_sources_rejects_unknown(self) -> None:
        from pydantic import ValidationError

        from fabrik.spec_loader import WatchdogConfig

        with pytest.raises(ValidationError, match="unknown trigger_sources"):
            WatchdogConfig(trigger_sources=["error_webhook", "bogus"])

    def test_negative_budget_rejected(self) -> None:
        """``ge=0.0`` on USD fields — negative budgets are nonsense."""
        from pydantic import ValidationError

        from fabrik.spec_loader import WatchdogConfig

        with pytest.raises(ValidationError):
            WatchdogConfig(daily_budget_usd=-1.0)
        with pytest.raises(ValidationError):
            WatchdogConfig(per_incident_budget_usd=-0.5)
        with pytest.raises(ValidationError):
            WatchdogConfig(daily_invocations_cap=-1)

    def test_spec_accepts_watchdog_block_from_yaml(self) -> None:
        """A spec YAML with a ``watchdog:`` block loads into ``Spec.watchdog``."""
        import yaml

        from fabrik.spec_loader import Spec

        yaml_doc = """
        id: testsvc
        template: python-api
        domain: test.vps1.ocoron.com
        watchdog:
          enabled: true
          daily_budget_usd: 2.5
          per_incident_budget_usd: 0.25
          auto_tier_b: true
        """
        spec = Spec.model_validate(yaml.safe_load(yaml_doc))
        assert spec.watchdog.enabled is True
        assert spec.watchdog.daily_budget_usd == 2.5
        assert spec.watchdog.per_incident_budget_usd == 0.25
        assert spec.watchdog.auto_tier_b is True
        # Unset fields stay at their defaults
        assert spec.watchdog.llm_provider_primary == "claude-code"

    def test_spec_default_watchdog_when_absent(self) -> None:
        """A spec without a ``watchdog:`` block gets the default (disabled) config."""
        import yaml

        from fabrik.spec_loader import Spec

        yaml_doc = """
        id: bare
        template: python-api
        domain: bare.vps1.ocoron.com
        """
        spec = Spec.model_validate(yaml.safe_load(yaml_doc))
        assert spec.watchdog.enabled is False
        assert spec.watchdog.daily_budget_usd == 1.0

    def test_spec_model_dump_roundtrip(self) -> None:
        """``Spec.model_dump`` → ``Spec.model_validate`` round-trip is stable."""
        import yaml

        from fabrik.spec_loader import Spec

        yaml_doc = """
        id: round
        template: python-api
        domain: round.vps1.ocoron.com
        watchdog:
          enabled: true
          daily_budget_usd: 3.0
        """
        spec = Spec.model_validate(yaml.safe_load(yaml_doc))
        dumped = spec.model_dump(exclude_none=True)
        # The dumped dict has all 13 watchdog keys (10 original + 3 added in
        # the artifact 1 amendment) even though only 2 were specified — same
        # pattern as every other defaulted sub-model (expose, source, etc.).
        assert "watchdog" in dumped
        assert dumped["watchdog"]["enabled"] is True
        assert dumped["watchdog"]["daily_budget_usd"] == 3.0
        assert dumped["watchdog"]["llm_provider_primary"] == "claude-code"  # default
        roundtrip = Spec.model_validate(dumped)
        assert roundtrip.watchdog == spec.watchdog

    # ──────────────────────────────────────────────────────────────────────
    # Artifact 1 amendment — v1 capability fields (locked 2026-06-02 during
    # artifact 2 review). Pins defaults + ranges so future refactors can't
    # silently weaken bleed-stop timing, accidentally enable PR-pushing on
    # uncoordinated projects, or disable doc lookups by default.
    # ──────────────────────────────────────────────────────────────────────

    def test_deadman_timeout_default_and_range(self) -> None:
        """Deadman timer: 300s default; 60s floor; 3600s ceiling.

        - 60s floor avoids alert storms (a re-alert every 60s for the same
          unresponded incident is the practical lower bound).
        - 3600s ceiling enforces "operator workflow sanity" — beyond 1 h the
          bleed-stop semantics stop being credible as a deadman.
        - 300s default = "5 minutes to acknowledge before we restart it for
          you" — the documented v1 trade-off between bleed limits and
          operator response latency.
        """
        from pydantic import ValidationError

        from fabrik.spec_loader import WatchdogConfig

        assert WatchdogConfig().deadman_timeout_seconds == 300
        # Floor: 59 rejected, 60 accepted
        with pytest.raises(ValidationError):
            WatchdogConfig(deadman_timeout_seconds=59)
        assert WatchdogConfig(deadman_timeout_seconds=60).deadman_timeout_seconds == 60
        # Ceiling: 3600 accepted, 3601 rejected
        assert WatchdogConfig(deadman_timeout_seconds=3600).deadman_timeout_seconds == 3600
        with pytest.raises(ValidationError):
            WatchdogConfig(deadman_timeout_seconds=3601)

    def test_external_docs_enabled_default_true(self) -> None:
        """External doc lookups (WebSearch + WebFetch) default ON.

        Doc lookups are the watchdog's most cost-effective diagnosis aid
        (an error-code lookup avoids many speculation calls), so the v1
        ship default is ON. The flag is the runtime gate; the
        claude-settings.json.template already declares the tools allowed
        and the 29-domain allow-list at the sandbox layer.
        """
        from fabrik.spec_loader import WatchdogConfig

        assert WatchdogConfig().external_docs_enabled is True
        assert WatchdogConfig(external_docs_enabled=False).external_docs_enabled is False

    def test_propose_fix_prs_default_false(self) -> None:
        """PR-proposal capability defaults OFF — opt-in per project.

        The sidecar can push to `watchdog/<incident_id>` branches when this
        is True. REQUIRES a pre-configured per-project git deploy key with
        a CODEOWNERS-enforced ruleset restricting Write to `watchdog/*`
        refs only. Off by default means a fresh `fabrik apply` cannot
        accidentally start pushing PRs on a repo that hasn't been wired
        for it. The deploy-key setup is operator work, not derivable from
        the spec, so the safe default is False.
        """
        from fabrik.spec_loader import WatchdogConfig

        assert WatchdogConfig().propose_fix_prs is False
        assert WatchdogConfig(propose_fix_prs=True).propose_fix_prs is True

    def test_amendment_fields_roundtrip_through_spec_yaml(self) -> None:
        """A spec YAML can set the 3 amendment fields and survive roundtrip."""
        import yaml

        from fabrik.spec_loader import Spec

        yaml_doc = """
        id: amend
        template: python-api
        domain: amend.vps1.ocoron.com
        watchdog:
          enabled: true
          daily_budget_usd: 1.5
          deadman_timeout_seconds: 120
          external_docs_enabled: false
          propose_fix_prs: true
        """
        spec = Spec.model_validate(yaml.safe_load(yaml_doc))
        assert spec.watchdog.deadman_timeout_seconds == 120
        assert spec.watchdog.external_docs_enabled is False
        assert spec.watchdog.propose_fix_prs is True
        # Roundtrip is stable
        roundtrip = Spec.model_validate(spec.model_dump(exclude_none=True))
        assert roundtrip.watchdog == spec.watchdog
