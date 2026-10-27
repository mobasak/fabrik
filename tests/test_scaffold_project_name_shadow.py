"""A project name must not shadow a third-party library the scaffolded server imports."""

import pytest

from fabrik.scaffold import _validate_project_name


@pytest.mark.parametrize("name", ["httpx", "fastapi", "redis", "sqlalchemy", "prometheus-client", "pydantic-settings"])
def test_library_shadowing_name_refused(name):
    with pytest.raises(ValueError, match="Reserved project name") as exc:
        _validate_project_name(name)
    assert "shadow" in str(exc.value)


def test_normal_name_accepted():
    _validate_project_name("acme-crm")
