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


@pytest.mark.parametrize("name", ["fastapi-user-auth", "audit-log"])
def test_a_project_named_after_a_vendored_module_is_rejected(name):
    """Its package would shadow the vendored module, and _write_server_lint_config excludes that
    name as vendored: the project's own code went unlinted and its mypy errors were swallowed
    (review of 10c243a6d)."""
    with pytest.raises(ValueError, match="vendored"):
        scaffold._validate_project_name(name)


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


# W-3e5a0e84: the rest of the class. Each validator guards a value that reaches SQL, a shell command,
# a provider API or a config file; each is called through its real function, a valid value first.
DRIVER_VALIDATORS = [
    ("fabrik.drivers.authelia", "_validate_domain", ("app.example.com",)),
    ("fabrik.drivers.authelia", "_validate_resources", (["^/api/"],)),
    ("fabrik.drivers.backrest", "_validate_db_name", ("mydb",)),
    ("fabrik.drivers.gatus", "_validate_project_name", ("my-app",)),
    ("fabrik.drivers.gatus", "_validate_domain", ("app.example.com",)),
    ("fabrik.drivers.glitchtip", "_validate_name", ("my-app",)),
    ("fabrik.drivers.meilisearch", "_validate_uid", ("my-index",)),
    ("fabrik.drivers.postgres", "_validate_identifier", ("mydb", "database")),
    ("fabrik.drivers.prometheus", "_validate_name", ("my-app",)),
    ("fabrik.drivers.prometheus", "_validate_domain", ("app.example.com",)),
    ("fabrik.drivers.redis", "_validate_service_name", ("my-app",)),
    ("fabrik.drivers.supabase", "_validate_table_name", ("users",)),
    ("fabrik.drivers.supabase", "_validate_column_name", ("email",)),
    ("fabrik.preplan", "_validate_slug", ("my-slug",)),
]


def _with_newline(args):
    first = args[0]
    first = [first[0] + "\n"] if isinstance(first, list) else first + "\n"
    return (first, *args[1:])


@pytest.mark.parametrize(
    ("module", "func", "args"),
    DRIVER_VALIDATORS,
    ids=[f"{m.rsplit('.', 1)[-1]}.{f}" for m, f, _ in DRIVER_VALIDATORS],
)
def test_an_identifier_with_a_trailing_newline_is_rejected(module, func, args):
    import importlib

    validate = getattr(importlib.import_module(module), func)
    validate(*args)  # the valid value passes
    with pytest.raises(ValueError):
        validate(*_with_newline(args))


def test_the_watchdog_role_script_rejects_a_db_name_with_a_newline():
    """provision_watchdog_ro interpolates the name into GRANT and \\c SQL."""
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "provision_watchdog_ro.py"
    spec = importlib.util.spec_from_file_location("provision_watchdog_ro", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod._validate_db_name("mydb") == "mydb"
    with pytest.raises(ValueError):
        mod._validate_db_name("mydb\n")


def test_a_pooled_bot_token_with_a_newline_is_skipped(tmp_path, monkeypatch):
    """The token is later substituted into a sed on .env.sysadmin; a newline there breaks the file."""
    import json

    from fabrik.orchestrator import sysadmin_tokens

    monkeypatch.setenv("FABRIK_DR_STORE", str(tmp_path))
    pool = sysadmin_tokens.pool_path()
    pool.parent.mkdir(parents=True)
    pool.write_text(
        json.dumps(
            {"pool": [{"label": "a", "token": "123:abc\n"}, {"label": "b", "token": "456:def"}]}
        )
    )

    assert sysadmin_tokens.claim_bot_token("vps9") == "456:def"


def test_a_gatus_health_path_with_a_control_character_is_rejected():
    """The path is appended to the probed URL; a newline makes the endpoint read as down forever."""
    from fabrik.drivers import gatus

    gatus._validate_health_path("/health")
    with pytest.raises(ValueError):
        gatus._validate_health_path("/health\n")


def test_a_reclaimed_bot_token_with_a_newline_is_not_returned(tmp_path, monkeypatch, caplog):
    """A token assigned before the check tightened must not reach the .env.sysadmin sed on a re-run."""
    import json

    from fabrik.orchestrator import sysadmin_tokens

    monkeypatch.setenv("FABRIK_DR_STORE", str(tmp_path))
    pool = sysadmin_tokens.pool_path()
    pool.parent.mkdir(parents=True)
    pool.write_text(
        json.dumps({"pool": [{"label": "a", "token": "123:abc\n", "assigned_to": "vps9"}]})
    )

    assert sysadmin_tokens.claim_bot_token("vps9") is None
    assert "malformed" in caplog.text
