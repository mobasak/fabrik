"""A scaffolded service's GlitchTip events carry its DSN, its release and its environment.

Mail 01M491AE33: scaffolded services shipped events with ``release=None`` and python-api/node-api
shipped none at all — their compose handed the container no ``SENTRY_DSN``. The chain graded here:
the deployer writes ``GIT_SHA``/``ENVIRONMENT``/``SENTRY_DSN`` into the app's ``.env``
(tests/orchestrator/test_deployer_git_sha.py), compose interpolates them into the container's
environment, and the GlitchTip init reads them into ``sentry_sdk.init``.

The compose half runs the REAL ``docker compose config`` (skipped when docker is absent); the init
half runs the real module with ``sentry_sdk.init`` replaced by a recorder.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Import THIS tree's package: the shared .venv resolves `fabrik` to the main checkout otherwise.
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import pytest  # noqa: E402

from fabrik import scaffold  # noqa: E402

SHA = "0123456789abcdef0123456789abcdef01234567"
DSN = "https://k@glitchtip.example/1"
# The names the chain reads; the test process's own values must never leak into a resolution.
_CHAIN_VARS = ("SENTRY_DSN", "GLITCHTIP_DSN", "GIT_SHA", "APP_GIT_SHA", "ENVIRONMENT", "APP_ENV")


def _load(path: Path, name: str = "svc"):
    src = path.read_text().replace("{pkg}", "svc").replace("{name}", name)
    target = path.parent / f"_loaded_{path.stem}.py"
    target.write_text(src)
    spec = importlib.util.spec_from_file_location(f"_loaded_{path.stem}_{id(target)}", target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _init_kwargs(module, monkeypatch, env: dict[str, str]) -> dict:
    """Run ``init_glitchtip()`` under *env* alone and return what reached ``sentry_sdk.init``."""
    import sentry_sdk

    for var in _CHAIN_VARS:
        monkeypatch.delenv(var, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    seen: dict = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: seen.update(kw))
    assert module.init_glitchtip() is True, "init_glitchtip took its no-op path"
    return seen


def _assert_this_tree() -> None:
    """The CODE comes from sys.path, but the TEMPLATES come from `fabrik.config.FABRIK_ROOT`,
    resolved once at import from `$FABRIK_ROOT` or the process CWD's worktree — so a run from
    another checkout grades that checkout's templates against this one's code."""
    from fabrik import config

    assert Path(scaffold.__file__).resolve().is_relative_to(REPO / "src"), (
        f"fabrik imported from {scaffold.__file__}, not {REPO / 'src'} — run with PYTHONPATH=src"
    )
    for label, path in (
        ("fabrik.config.FABRIK_ROOT", config.FABRIK_ROOT),
        ("fabrik.scaffold.TEMPLATE_DIR", scaffold.TEMPLATE_DIR),
    ):
        assert Path(path).resolve().is_relative_to(REPO.resolve()), (
            f"{label} = {path} is outside this repo ({REPO}): the scaffold would read another "
            f"checkout's templates. Run pytest from {REPO}, or set FABRIK_ROOT={REPO}."
        )


@pytest.fixture(autouse=True)
def _this_tree() -> None:
    _assert_this_tree()


def test_fabrik_resolves_to_this_tree() -> None:
    """A green run against the main checkout's package or templates would grade the wrong code."""
    _assert_this_tree()


@pytest.mark.parametrize(
    ("env", "release", "environment"),
    [
        ({"APP_GIT_SHA": SHA, "GIT_SHA": "f" * 40}, SHA, "production"),
        ({"APP_GIT_SHA": "unknown", "GIT_SHA": SHA}, SHA, "production"),
        ({"APP_GIT_SHA": "  ", "GIT_SHA": f" {SHA} "}, SHA, "production"),
        ({"APP_GIT_SHA": "unknown"}, None, "production"),
        ({"GIT_SHA": "unknown"}, None, "production"),
        ({"APP_ENV": "staging", "ENVIRONMENT": "dev"}, None, "staging"),
        ({"APP_ENV": " ", "ENVIRONMENT": "dev"}, None, "dev"),
        ({"ENVIRONMENT": "  "}, None, "production"),
    ],
)
def test_init_glitchtip_release_and_environment_rules(
    tmp_path, monkeypatch, env, release, environment
) -> None:
    template = REPO / "templates" / "scaffold" / "python" / "glitchtip_init.py"
    copy = tmp_path / "glitchtip_init.py"
    shutil.copy(template, copy)
    seen = _init_kwargs(_load(copy), monkeypatch, {"SENTRY_DSN": DSN, **env})
    assert seen["release"] == release
    assert seen["environment"] == environment


_DEPLOYER_ENV = f"SENTRY_DSN={DSN}\nGIT_SHA={SHA}\nENVIRONMENT=staging\nLOG_LEVEL=INFO\n"


def _compose_env(project: Path, service: str, dotenv: str = _DEPLOYER_ENV) -> dict[str, str]:
    """Resolve the scaffolded compose against a deployer-shaped ``.env`` with real docker compose."""
    if (
        shutil.which("docker") is None
        or subprocess.run(
            ["docker", "compose", "version"], capture_output=True, check=False
        ).returncode
        != 0
    ):
        pytest.skip("docker compose is not available")
    (project / ".env").write_text(dotenv)
    clean = {k: v for k, v in os.environ.items() if k not in _CHAIN_VARS}
    out = subprocess.run(
        ["docker", "compose", "-f", "compose.yaml", "config", "--format", "json"],
        cwd=project,
        env=clean,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout
    env = json.loads(out)["services"][service]["environment"]
    return {k: ("" if v is None else str(v)) for k, v in env.items()}


def test_python_api_compose_delivers_dsn_release_environment(tmp_path, monkeypatch) -> None:
    project = tmp_path / "svc"
    project.mkdir()
    scaffold._scaffold_python_api(project, "svc", "a test service")
    env = _compose_env(project, "svc")
    assert env["SENTRY_DSN"] == DSN
    assert env["APP_GIT_SHA"] == SHA
    assert env["ENVIRONMENT"] == "staging"

    # …and the emitted module turns exactly that container env into the init.
    module = _load(project / "src" / "svc" / "glitchtip_init.py")
    seen = _init_kwargs(module, monkeypatch, {k: v for k, v in env.items() if k in _CHAIN_VARS})
    assert (seen["dsn"], seen["release"], seen["environment"]) == (DSN, SHA, "staging")


def test_python_api_compose_without_a_sha_ships_no_release(tmp_path, monkeypatch) -> None:
    """The compose default is the literal "unknown" — it must never become a release."""
    project = tmp_path / "svc"
    project.mkdir()
    scaffold._scaffold_python_api(project, "svc", "a test service")
    env = _compose_env(project, "svc", dotenv=f"SENTRY_DSN={DSN}\n")
    assert env["APP_GIT_SHA"] == "unknown"
    assert env["ENVIRONMENT"] == "production"
    module = _load(project / "src" / "svc" / "glitchtip_init.py")
    seen = _init_kwargs(module, monkeypatch, {k: v for k, v in env.items() if k in _CHAIN_VARS})
    assert (seen["release"], seen["environment"]) == (None, "production")


_NODE_PROBE = """
import {{ glitchtipRelease, glitchtipEnvironment }} from {url};
process.stdout.write(JSON.stringify({{
  release: glitchtipRelease() ?? null,
  environment: glitchtipEnvironment(),
  cases: {cases}.map((env) => [glitchtipRelease(env) ?? null, glitchtipEnvironment(env)]),
}}));
"""

_NODE_CASES = [
    ({"APP_GIT_SHA": "unknown", "GIT_SHA": SHA}, [SHA, "production"]),
    ({"APP_GIT_SHA": " ", "GIT_SHA": "unknown"}, [None, "production"]),
    ({"APP_GIT_SHA": SHA, "GIT_SHA": "f" * 40, "APP_ENV": "qa", "ENVIRONMENT": "dev"}, [SHA, "qa"]),
    ({"APP_ENV": "  ", "ENVIRONMENT": "dev"}, [None, "dev"]),
]


def test_node_api_compose_and_module_read_the_release(tmp_path) -> None:
    project = tmp_path / "svc"
    project.mkdir()
    scaffold._scaffold_node_api(project, "svc", "a test service")
    env = _compose_env(project, "svc")
    assert env["SENTRY_DSN"] == DSN
    assert env["APP_GIT_SHA"] == SHA
    assert env["ENVIRONMENT"] == "staging"

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available")
    module = project / "src" / "glitchtip_init.js"
    probe = _NODE_PROBE.format(
        url=json.dumps(module.as_uri()),
        cases=json.dumps([case for case, _ in _NODE_CASES]),
    )
    # The container env, minus the DSN: with a DSN the module would import @sentry/node, which a
    # bare scaffold has not installed. The release/environment readers do not depend on it.
    run_env = {k: v for k, v in os.environ.items() if k not in _CHAIN_VARS}
    run_env.update({k: v for k, v in env.items() if k in _CHAIN_VARS and "DSN" not in k})
    out = subprocess.run(
        [node, "--input-type=module", "-e", probe],
        cwd=project,
        env=run_env,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout
    got = json.loads(out)
    assert (got["release"], got["environment"]) == (SHA, "staging")
    assert got["cases"] == [expected for _, expected in _NODE_CASES]
