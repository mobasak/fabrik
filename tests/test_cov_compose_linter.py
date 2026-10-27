"""Coverage tests for fabrik.compose_linter (hermetic, pure-string input)."""

import pytest

from fabrik.compose_linter import ComposeLinter, LintResult, validate_compose

GOOD = """
services:
  web:
    image: nginx:1
    container_name: web
    restart: unless-stopped
"""


@pytest.fixture
def linter():
    return ComposeLinter()


def test_clean_compose_is_valid_without_warnings(linter):
    r = linter.lint(GOOD)
    assert isinstance(r, LintResult)
    assert r.valid is True
    assert r.errors == []
    assert r.warnings == []


def test_invalid_yaml_reports_error(linter):
    r = linter.lint("services: [unclosed")
    assert r.valid is False
    assert r.errors and r.errors[0].startswith("Invalid YAML")
    assert r.warnings == []


@pytest.mark.parametrize("text", ["", "# only a comment\n", "version: '3'\n", "- a\n- b\n"])
def test_missing_services_key(linter, text):
    r = linter.lint(text)
    assert r.valid is False
    assert r.errors == ["Missing 'services' key"]


def test_missing_container_name_warns_only(linter):
    r = linter.lint("services:\n  web:\n    image: nginx\n    restart: always\n")
    assert r.valid is True
    assert len(r.warnings) == 1
    assert "Service 'web'" in r.warnings[0] and "container_name" in r.warnings[0]


def test_missing_restart_warns_only(linter):
    r = linter.lint("services:\n  web:\n    image: nginx\n    container_name: web\n")
    assert r.valid is True
    assert len(r.warnings) == 1
    assert "restart" in r.warnings[0]


def test_both_missing_gives_two_warnings(linter):
    r = linter.lint("services:\n  web:\n    image: nginx\n")
    assert len(r.warnings) == 2


@pytest.mark.parametrize("image", ["postgres:16", "MySQL:8", "mariadb", "mongo:7", "redis:7"])
def test_database_without_healthcheck_warns(linter, image):
    yml = f"services:\n  db:\n    image: {image}\n    container_name: db\n    restart: always\n"
    r = linter.lint(yml)
    assert r.valid is True
    assert len(r.warnings) == 1
    assert "healthcheck" in r.warnings[0]


def test_database_with_healthcheck_no_warning(linter):
    yml = (
        "services:\n  db:\n    image: postgres:16\n    container_name: db\n"
        "    restart: always\n    healthcheck:\n      test: ['CMD', 'true']\n"
    )
    assert linter.lint(yml).warnings == []


def test_non_database_image_no_healthcheck_warning(linter):
    r = linter.lint(GOOD)
    assert not any("healthcheck" in w for w in r.warnings)


def test_service_without_image_does_not_crash(linter):
    r = linter.lint("services:\n  app:\n    build: .\n    container_name: a\n    restart: always\n")
    assert r.valid is True and r.warnings == []


def test_non_dict_service_is_skipped(linter):
    r = linter.lint("services:\n  weird: just-a-string\n")
    assert r.valid is True
    assert r.warnings == []


def test_warnings_name_each_service(linter):
    r = linter.lint("services:\n  a:\n    image: x\n  b:\n    image: y\n")
    assert any("'a'" in w for w in r.warnings)
    assert any("'b'" in w for w in r.warnings)


def test_unresolved_var_is_error(linter):
    yml = GOOD + "    environment:\n      PW: ${DB_PASSWORD}\n"
    r = linter.lint(yml)
    assert r.valid is False
    assert len(r.errors) == 1
    assert "DB_PASSWORD" in r.errors[0]


def test_var_with_default_is_ok(linter):
    yml = GOOD + "    environment:\n      PW: ${DB_PASSWORD:-secret}\n"
    assert linter.lint(yml).valid is True


def test_var_required_syntax_is_ok(linter):
    yml = GOOD + "    environment:\n      PW: ${DB_PASSWORD:?}\n"
    assert linter.lint(yml).valid is True


def test_unresolved_vars_sorted_and_deduped(linter):
    assert linter._find_unresolved_vars("${ZED} ${ALPHA} ${ZED}") == ["ALPHA", "ZED"]


def test_find_unresolved_mixed_forms(linter):
    text = "${A} ${B:-x} ${C:?} ${D}"
    assert linter._find_unresolved_vars(text) == ["A", "D"]


def test_find_unresolved_none(linter):
    assert linter._find_unresolved_vars("no vars $HOME here") == []


def test_lowercase_var_not_flagged(linter):
    assert linter._find_unresolved_vars("${lower}") == []


def test_unresolved_var_error_lists_all(linter):
    yml = GOOD + "    environment:\n      A: ${ONE}\n      B: ${TWO}\n"
    r = linter.lint(yml)
    assert "ONE, TWO" in r.errors[0]


def test_lint_and_raise_ok(linter):
    assert linter.lint_and_raise(GOOD) is None


def test_lint_and_raise_raises_on_unresolved(linter):
    with pytest.raises(ValueError, match="Compose validation failed.*FOO"):
        linter.lint_and_raise(GOOD + "    command: ${FOO}\n")


def test_lint_and_raise_raises_on_bad_yaml(linter):
    with pytest.raises(ValueError, match="Invalid YAML"):
        linter.lint_and_raise("a: [")


def test_lint_and_raise_ignores_warnings(linter):
    linter.lint_and_raise("services:\n  web:\n    image: nginx\n")


def test_validate_compose_matches_linter():
    text = GOOD + "    command: ${X}\n"
    assert validate_compose(text) == ComposeLinter().lint(text)
    assert validate_compose(GOOD).valid is True


@pytest.mark.xfail(strict=True, reason="image: null crashes with AttributeError (None.lower())")
def test_null_image_does_not_crash(linter):
    r = linter.lint("services:\n  app:\n    image:\n    container_name: a\n    restart: always\n")
    assert r.valid is True


@pytest.mark.xfail(strict=True, reason="services: null crashes with AttributeError (None.items())")
def test_null_services_reported_not_crash(linter):
    r = linter.lint("services:\n")
    assert r.valid is False or r.valid is True  # must return a LintResult, not raise
