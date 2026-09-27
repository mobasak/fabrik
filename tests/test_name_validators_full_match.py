"""Identifier validators must match the WHOLE string (W-479028c8).

`re.match(r"^...$", s)` lets a trailing newline through, because `$` also matches just before a
final "\n". A project name built into package names, file paths and emitted code, or an app name
built into an SSH shell command, must never carry one.
"""

import pytest

import fabrik.drivers.ssh as ssh_driver
import fabrik.scaffold as scaffold
from fabrik.orchestrator.destroyer import _destroy_compose


@pytest.mark.parametrize("name", ["ok-name\n", "ok\nname", "\nok"])
def test_project_name_with_a_newline_is_rejected(name):
    with pytest.raises(ValueError, match="Invalid project name"):
        scaffold._validate_project_name(name)


def test_a_plain_project_name_still_passes():
    scaffold._validate_project_name("ok-name")


def test_destroy_refuses_an_app_name_with_a_trailing_newline_before_any_ssh(monkeypatch):
    calls = []
    monkeypatch.setattr(ssh_driver, "ssh", lambda cmd, **_kw: calls.append(cmd) or "")

    result = _destroy_compose("some-app\n", dry_run=False)

    assert result.status == "error", result
    assert calls == [], f"an invalid name reached the remote shell: {calls}"


def test_deployer_refuses_an_app_name_with_a_trailing_newline():
    """The deployer's twin of the destroy check guards the same SSH commands."""
    from fabrik.orchestrator.deployer_ssh import DeployError, _validate_name

    with pytest.raises(DeployError, match="Invalid app name"):
        _validate_name("some-app\n")
    _validate_name("some-app")
