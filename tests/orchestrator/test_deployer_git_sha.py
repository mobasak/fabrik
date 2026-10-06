"""The git deploy persists the deployed commit as ``GIT_SHA`` in the app's ``.env``.

A scaffolded service labels its GlitchTip events with ``release`` = the git SHA it runs, read from
``APP_GIT_SHA`` (compose: ``${GIT_SHA:-unknown}``) — so the SHA must live in the ``.env`` compose
interpolates from, and survive every later ``.env`` rewrite (mail 01M491AE33).

Everything is driven through the ``fabrik.drivers.ssh.ssh`` seam with a recording fake and a
patched ``_write_file_to_vps``; nothing reaches a host.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import patch

# Import THIS tree's package: the shared .venv resolves `fabrik` to the main checkout otherwise.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest  # noqa: E402

from fabrik.orchestrator import deployer_ssh  # noqa: E402
from fabrik.orchestrator.context import DeploymentContext  # noqa: E402
from fabrik.orchestrator.deployer_ssh import SSHDeployer, _parse_env  # noqa: E402
from fabrik.orchestrator.exceptions import DeployError  # noqa: E402

OLD = "a" * 40
NEW = "b" * 40
RETURNS_NONE = object()  # a `rev_parse` answer: the ssh seam returns None instead of a str


class _Vps:
    """A fake VPS: one app dir with a git HEAD and a ``.env``; records every command."""

    def __init__(
        self,
        env: str | None,
        head: str = OLD,
        pulled: str = NEW,
        rev_parse: str | Exception | object | None = None,
        fail_first_up: bool = False,
    ) -> None:
        self.env = env
        self.head = head
        self.pulled = pulled
        self.rev_parse = rev_parse  # overrides what `rev-parse HEAD` answers AFTER the pull
        self.has_pulled = False
        self.fail_first_up = fail_first_up
        self.calls: list[str] = []
        self.writes: list[str] = []

    def ssh(self, cmd: str, timeout: int = 0) -> str:
        self.calls.append(cmd)
        if "echo present" in cmd:
            return "absent" if self.env is None else "present"
        if cmd.startswith("sudo cat ") and cmd.rstrip().endswith(".env"):
            return self.env or ""
        if "test -d" in cmd and ".git" in cmd:
            return "exists"
        if "git pull" in cmd:
            self.head = self.pulled
            self.has_pulled = True
            return ""
        if "git reset --hard " in cmd:
            self.head = cmd.rsplit(" ", 1)[-1]
            return ""
        if "rev-parse HEAD" in cmd:
            if self.has_pulled and self.rev_parse is not None:
                if isinstance(self.rev_parse, Exception):
                    raise self.rev_parse
                if self.rev_parse is RETURNS_NONE:
                    return None  # a malformed seam answer, not a string
                return self.rev_parse + "\n"
            return self.head + "\n"
        if "compose up" in cmd and self.fail_first_up:
            self.fail_first_up = False
            raise RuntimeError("container unhealthy")
        return ""

    def write(self, name: str, filename: str, content: str) -> None:
        assert filename == ".env", filename
        self.calls.append("<.env written>")
        self.writes.append(content)
        self.env = content

    def last_env(self) -> dict[str, str]:
        assert self.writes, "no .env was written"
        return _parse_env(self.writes[-1])


def _ctx(env: dict[str, str]) -> DeploymentContext:
    ctx = DeploymentContext(spec_path=Path("test.yaml"))
    ctx.spec = {
        "name": "my-app",
        "source": {"type": "git", "repository": "https://example.invalid/r.git"},
        "env": dict(env),
    }
    ctx.secrets = {}
    ctx.minted_secrets = {}
    return ctx


def _patched(vps: _Vps):
    return (
        patch("fabrik.drivers.ssh.ssh", vps.ssh),
        patch.object(deployer_ssh, "_write_file_to_vps", vps.write),
        patch.object(deployer_ssh, "_read_compose_from_vps", lambda name: "services: {}\n"),
        patch.object(deployer_ssh, "_validate_compose", lambda content: []),
        patch.object(deployer_ssh, "_assert_claude_cli_mounts", lambda content, spec: None),
        patch.object(deployer_ssh, "_compose_up", lambda name, disabled, ssh_fn: None),
        patch.object(SSHDeployer, "find_existing", lambda self, name: {"name": name}),
    )


def _apply(vps: _Vps, ctx: DeploymentContext) -> None:
    p = _patched(vps)
    with p[0], p[1], p[2], p[3], p[4], p[5], p[6]:
        SSHDeployer().deploy(ctx)


def test_fabrik_resolves_to_this_tree() -> None:
    """A green run against the main checkout's package would grade the wrong code."""
    assert (
        Path(deployer_ssh.__file__)
        .resolve()
        .is_relative_to(Path(__file__).resolve().parents[2] / "src")
    ), deployer_ssh.__file__


def test_deploy_git_persists_the_sha_over_a_blank_spec_value() -> None:
    vps = _Vps("SENTRY_DSN=https://k@glitchtip.example/1\n")
    _apply(vps, _ctx({"GIT_SHA": "", "LOG_LEVEL": "INFO"}))
    env = vps.last_env()
    assert env["GIT_SHA"] == NEW
    # The rest of the merge is untouched: registrar keys kept, spec keys applied.
    assert env["SENTRY_DSN"] == "https://k@glitchtip.example/1"
    assert env["LOG_LEVEL"] == "INFO"
    # The SHA is read AFTER the pull, so it names the code about to be built.
    pull = next(i for i, c in enumerate(vps.calls) if "git pull" in c)
    rev = next(i for i, c in enumerate(vps.calls) if "rev-parse HEAD" in c)
    assert rev > pull


def test_a_secret_still_outranks_the_sha_override() -> None:
    vps = _Vps(None)
    ctx = _ctx({})
    ctx.secrets = {"GIT_SHA": "c" * 40}
    _apply(vps, ctx)
    assert vps.last_env()["GIT_SHA"] == "c" * 40


def test_dsn_injection_keeps_the_sha() -> None:
    vps = _Vps("LOG_LEVEL=INFO\n")
    ctx = _ctx({"GIT_SHA": ""})
    _apply(vps, ctx)
    ctx.app_name = "my-app"
    p = _patched(vps)
    with p[0], p[1], p[5]:
        SSHDeployer().inject_env(ctx, {"SENTRY_DSN": "https://k@glitchtip.example/1"})
    env = vps.last_env()
    assert env["SENTRY_DSN"] == "https://k@glitchtip.example/1"
    assert env["GIT_SHA"] == NEW


def test_a_spec_interpolation_literal_never_clobbers_a_real_value() -> None:
    """A generated spec copies compose's `SENTRY_DSN: ${SENTRY_DSN:-}` into env:. On a re-apply
    that literal must not overwrite the registrar's real DSN in .env (it would blank reporting
    until the registrar re-injects); on a first deploy there is nothing to keep, so it is written."""
    spec_env = {
        "SENTRY_DSN": "${SENTRY_DSN:-}",
        "LOG_LEVEL": "${LOG_LEVEL:-INFO}",
        "APP_GIT_SHA": "${GIT_SHA}",
        "GIT_SHA": "${GIT_SHA:-unknown}",
    }
    vps = _Vps("SENTRY_DSN=https://k@g/1\nLOG_LEVEL=DEBUG\nAPP_GIT_SHA=abc\n")
    _apply(vps, _ctx(spec_env))
    env = vps.last_env()
    assert env["SENTRY_DSN"] == "https://k@g/1"
    assert env["LOG_LEVEL"] == "DEBUG"
    assert env["APP_GIT_SHA"] == "abc"
    assert env["GIT_SHA"] == NEW  # the deploy-time override still wins over the spec literal

    first = _Vps(None)
    _apply(first, _ctx(spec_env))
    env = first.last_env()
    assert env["SENTRY_DSN"] == "${SENTRY_DSN:-}"
    assert env["LOG_LEVEL"] == "${LOG_LEVEL:-INFO}"
    assert env["GIT_SHA"] == NEW


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("${SENTRY_DSN:-}", True),
        ("${LOG_LEVEL:-INFO}", True),
        ("${GIT_SHA}", True),
        ("${X-default}", True),
        ("https://k@g/1", False),
        ("prefix-${X}", False),
        ("${X}-suffix", False),
        ("${X}${Y}", False),
        ("${1BAD}", False),
        ("", False),
    ],
)
def test_is_placeholder_recognises_one_bare_interpolation(value, expected) -> None:
    assert deployer_ssh._is_placeholder(value) is expected


def test_redeploy_and_rollback_persist_their_sha() -> None:
    # Success: the pulled SHA lands in .env before the stack comes up.
    vps = _Vps("GIT_SHA=" + OLD + "\nSENTRY_DSN=x\n")
    p = _patched(vps)
    with p[0], p[1]:
        SSHDeployer().redeploy("my-app", source_type="git")
    env = vps.last_env()
    assert env["GIT_SHA"] == NEW
    assert env["SENTRY_DSN"] == "x"
    order = [c for c in vps.calls if "git pull" in c or "compose up" in c or c == "<.env written>"]
    assert order[0].endswith("git pull") and order[1] == "<.env written>", order
    assert "compose up" in order[2], order

    # Rollback: the health check fails, the code is reset, and .env names the code now running.
    vps = _Vps("GIT_SHA=" + OLD + "\nSENTRY_DSN=x\n", fail_first_up=True)
    p = _patched(vps)
    with p[0], p[1], pytest.raises(DeployError, match="rolled back"):
        SSHDeployer().redeploy("my-app", source_type="git")
    assert [_parse_env(w)["GIT_SHA"] for w in vps.writes] == [NEW, OLD]
    assert vps.last_env()["SENTRY_DSN"] == "x"


@pytest.mark.parametrize(
    "answer",
    [
        RuntimeError("fatal: not a git repository"),
        "fatal: ambiguous argument 'HEAD'",
        "B" * 40,
        OLD[:39],
        "",
        RETURNS_NONE,
    ],
    ids=["raises", "error-text", "uppercase", "short", "empty", "seam-returns-none"],
)
def test_unreadable_sha_leaves_env_alone(answer, caplog) -> None:
    # apply: the deploy proceeds, and .env keeps the GIT_SHA it already had.
    vps = _Vps("GIT_SHA=" + OLD + "\n", rev_parse=answer)
    with caplog.at_level(logging.WARNING, logger="fabrik.orchestrator.deployer_ssh"):
        _apply(vps, _ctx({"LOG_LEVEL": "INFO"}))
    assert vps.last_env()["GIT_SHA"] == OLD
    assert any("compose build" in c for c in vps.calls)
    assert any("compose up" in c for c in vps.calls)
    assert "GIT_SHA" in caplog.text

    # redeploy: nothing is written and the redeploy still completes.
    vps = _Vps("GIT_SHA=" + OLD + "\n", rev_parse=answer)
    p = _patched(vps)
    caplog.clear()
    with p[0], p[1], caplog.at_level(logging.WARNING, logger="fabrik.orchestrator.deployer_ssh"):
        SSHDeployer().redeploy("my-app", source_type="git")
    assert vps.writes == []
    assert any("compose up" in c for c in vps.calls)
    assert "GIT_SHA" in caplog.text
