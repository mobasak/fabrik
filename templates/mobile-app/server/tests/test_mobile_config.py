"""Tests for mobile-config — force-update gate, kill-switch, feature toggles."""

from __future__ import annotations

from mobile_config import AppConfig, evaluate, is_feature_enabled


def _config(**kwargs) -> AppConfig:
    base = {
        "min_version": {"ios": "1.2.0", "android": "1.2.0"},
        "latest_version": {"ios": "1.5.0", "android": "1.5.0"},
    }
    base.update(kwargs)
    return AppConfig(**base)


def test_below_min_forces_update():
    r = evaluate(_config(), platform="ios", app_version="1.1.0")
    assert r.update_required
    assert r.update_available  # below latest too


def test_between_min_and_latest_is_soft_update_only():
    r = evaluate(_config(), platform="ios", app_version="1.3.0")
    assert not r.update_required
    assert r.update_available


def test_at_latest_needs_no_update():
    r = evaluate(_config(), platform="ios", app_version="1.5.0")
    assert not r.update_required
    assert not r.update_available


def test_semver_ordering_not_string_compare():
    # 1.10.0 > 1.5.0 numerically (string compare would call "1.10.0" < "1.5.0").
    r = evaluate(_config(), platform="ios", app_version="1.10.0")
    assert not r.update_required
    assert not r.update_available


def test_exact_min_is_not_below_min():
    r = evaluate(_config(), platform="ios", app_version="1.2.0")
    assert not r.update_required  # strictly-below, so == min is fine


def test_malformed_client_version_never_hard_blocks():
    r = evaluate(_config(), platform="ios", app_version="garbage")
    assert not r.update_required  # never brick a user over a bad version string
    assert r.update_available  # but nudge (a latest is configured)


def test_malformed_version_no_latest_configured_no_nudge():
    r = evaluate(AppConfig(min_version={"ios": "1.2.0"}), platform="ios", app_version="???")
    assert not r.update_required
    assert not r.update_available


def test_unknown_platform_never_blocks():
    r = evaluate(_config(), platform="web", app_version="0.0.1")
    assert not r.update_required
    assert not r.update_available
    assert r.min_version is None


def test_kill_switch_propagates():
    r = evaluate(_config(kill_switch=True, kill_switch_message="Back at 5pm"), platform="ios", app_version="1.5.0")
    assert r.kill_switch
    assert r.kill_switch_message == "Back at 5pm"


def test_features_and_paywall_propagate():
    r = evaluate(
        _config(features={"new_home": True, "beta": False}, paywall_id="pw_2"),
        platform="ios",
        app_version="1.5.0",
    )
    assert r.features == {"new_home": True, "beta": False}
    assert r.paywall_id == "pw_2"


def test_prerelease_is_below_release():
    # 1.5.0rc1 < 1.5.0 per PEP 440, so an rc build below min is caught.
    r = evaluate(_config(), platform="ios", app_version="1.2.0rc1")
    assert r.update_required


def test_is_feature_enabled_absent_is_off():
    config = _config(features={"a": True})
    assert is_feature_enabled(config, "a")
    assert not is_feature_enabled(config, "missing")


def test_to_dict_shape():
    r = evaluate(_config(features={"x": True}, paywall_id="pw"), platform="ios", app_version="1.3.0")
    d = r.to_dict()
    assert d == {
        "update_required": False,
        "update_available": True,
        "kill_switch": False,
        "kill_switch_message": None,
        "features": {"x": True},
        "paywall_id": "pw",
        "min_version": "1.2.0",
        "latest_version": "1.5.0",
    }


def test_from_dict_tolerates_missing_keys():
    config = AppConfig.from_dict({"min_version": {"ios": "2.0.0"}})
    assert config.min_version == {"ios": "2.0.0"}
    assert config.latest_version == {}
    assert config.kill_switch is False
    assert config.features == {}
    # and it evaluates
    r = evaluate(config, platform="ios", app_version="1.0.0")
    assert r.update_required


# --------------------------------------------------------------------------
# Regression guards for the /fabrik-review findings
# --------------------------------------------------------------------------


def test_non_string_config_version_does_not_crash():
    """M1: a numeric stored version must degrade (gate off), not TypeError the endpoint."""
    config = AppConfig(min_version={"ios": 1.2}, latest_version={})  # type: ignore[dict-item]
    r = evaluate(config, platform="ios", app_version="1.0.0")
    assert not r.update_required  # unparsable min ⇒ gate disabled, no crash


def test_from_dict_non_mapping_fields_degrade_safely():
    """M2: list/garbage stored fields become empty — no crash, no silent corruption."""
    config = AppConfig.from_dict({"min_version": ["1.2.0", "1.3.0"], "features": ["a", "b"]})
    assert config.min_version == {}
    assert config.features == {}


def test_string_kill_switch_false_does_not_engage():
    """M3: bool('false') is True in Python — the kill-switch must NOT trust that."""
    assert AppConfig.from_dict({"kill_switch": "false"}).kill_switch is False
    assert AppConfig.from_dict({"kill_switch": "0"}).kill_switch is False
    assert AppConfig.from_dict({"kill_switch": "true"}).kill_switch is True
    assert AppConfig.from_dict({"kill_switch": True}).kill_switch is True


def test_from_dict_coerces_feature_bool_strings():
    config = AppConfig.from_dict({"features": {"a": "true", "b": "false", "c": True}})
    assert config.features == {"a": True, "b": False, "c": True}


def test_invalid_versions_detects_operator_typo():
    """M4: a malformed config version is lintable, and evaluate fails open (documented)."""
    config = AppConfig(min_version={"ios": "not-a-version"}, latest_version={"ios": "1.5.0"})
    assert config.invalid_versions() == ["not-a-version"]
    assert not evaluate(config, platform="ios", app_version="0.0.1").update_required


def test_invalid_versions_clean_config_is_empty():
    assert _config().invalid_versions() == []


def test_platform_lookup_is_case_insensitive():
    """M5: config authored 'iOS' must still gate an 'ios' client."""
    config = AppConfig(min_version={"iOS": "2.0.0"}, latest_version={"iOS": "2.0.0"})
    assert evaluate(config, platform="ios", app_version="1.0.0").update_required


def test_build_metadata_version_compares_by_release():
    # 1.2.0+build == 1.2.0 for ordering (PEP 440 ignores build metadata in comparison).
    assert not evaluate(_config(), platform="ios", app_version="1.2.0+build123").update_required


def test_nan_kill_switch_does_not_engage():
    """C1: NaN != 0 is True — the kill-switch must reject NaN, not black out the app."""
    assert AppConfig.from_dict({"kill_switch": float("nan")}).kill_switch is False


def test_invalid_versions_flags_non_string_config_value():
    """C2: a non-str configured version is a dead gate — the lint must report it."""
    config = AppConfig(min_version={"ios": 1.2}, latest_version={})  # type: ignore[dict-item]
    assert config.invalid_versions() == ["1.2"]


def test_from_dict_full_roundtrip():
    data = {
        "min_version": {"ios": "1.0.0"},
        "latest_version": {"ios": "2.0.0"},
        "kill_switch": True,
        "kill_switch_message": "maint",
        "features": {"f": True},
        "paywall_id": "pw1",
    }
    config = AppConfig.from_dict(data)
    r = evaluate(config, platform="ios", app_version="1.5.0")
    assert r.kill_switch and r.update_available and not r.update_required
    assert r.features == {"f": True} and r.paywall_id == "pw1"
