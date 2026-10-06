"""Mint-once: a secret the hub INVENTED never replaces the value the deployed ``.env`` holds.

W-023bdd59 — ``SecretsManager`` mints a fresh value for a ``generate``/``required`` key the hub cannot
resolve, and the hub never keeps the value it minted on the first apply (that value went only into the
remote ``/opt/<app>/.env``). Every re-apply therefore rendered and wrote a NEW value — for a
stable-forever key (Zitadel's ``ZITADEL_MASTERKEY``) the stored data becomes unreadable. The deployer
now swaps each minted value for the deployed one BEFORE any source path renders: the template path
bakes ``ctx.secrets`` into ``compose.yaml`` literals, which outrank ``.env``.

Everything is driven through the ``fabrik.drivers.ssh.ssh`` seam and a fake secrets manager; nothing
reaches a host.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from fabrik.orchestrator import DeploymentOrchestrator
from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.deployer_ssh import SSHDeployer
from fabrik.orchestrator.exceptions import DeployError
from fabrik.spec_loader import SourceType


def _ctx(spec: dict, secrets: dict[str, str], minted: dict[str, str]) -> DeploymentContext:
    ctx = DeploymentContext(spec_path=Path("test.yaml"))
    ctx.spec = spec
    ctx.secrets = dict(secrets)
    ctx.minted_secrets = dict(minted)
    return ctx


class _Ssh:
    """Fake ssh: answers the `.env` probe and cat, records every command it was asked to run."""

    def __init__(self, remote_env: str | None, fail: bool = False) -> None:
        self.remote_env = remote_env
        self.fail = fail
        self.calls: list[str] = []

    def __call__(self, cmd: str, timeout: int = 0) -> str:
        self.calls.append(cmd)
        if self.fail:
            raise RuntimeError("ssh: connection reset")
        if "echo present" in cmd:
            return "absent" if self.remote_env is None else "present"
        if cmd.startswith("sudo cat "):
            return self.remote_env or ""
        return ""


def _preserve(ctx: DeploymentContext, ssh: _Ssh, source: dict | None = None,
              source_type: SourceType = SourceType.TEMPLATE) -> None:
    with patch("fabrik.drivers.ssh.ssh", ssh):
        SSHDeployer()._preserve_minted_secrets(ctx, "my-app", source or {}, source_type)


def test_reapply_keeps_the_deployed_value_of_a_minted_secret() -> None:
    ctx = _ctx({"name": "my-app"}, {"MASTERKEY": "fresh"}, {"MASTERKEY": "fresh"})
    _preserve(ctx, _Ssh("MASTERKEY=first-apply\n"))
    assert ctx.secrets["MASTERKEY"] == "first-apply"


def test_first_deploy_keeps_the_minted_value() -> None:
    ctx = _ctx({"name": "my-app"}, {"MASTERKEY": "fresh"}, {"MASTERKEY": "fresh"})
    _preserve(ctx, _Ssh(None))
    assert ctx.secrets["MASTERKEY"] == "fresh"


def test_a_hub_supplied_secret_still_wins() -> None:
    ctx = _ctx({"name": "my-app"}, {"API_KEY": "rotated"}, {})
    ssh = _Ssh("API_KEY=old\n")
    _preserve(ctx, ssh)
    assert ctx.secrets["API_KEY"] == "rotated"
    assert ssh.calls == []  # nothing minted ⇒ no remote read at all


def test_an_empty_deployed_value_is_filled_by_the_mint() -> None:
    ctx = _ctx({"name": "my-app"}, {"MASTERKEY": "fresh"}, {"MASTERKEY": "fresh"})
    _preserve(ctx, _Ssh("MASTERKEY=\n"))
    assert ctx.secrets["MASTERKEY"] == "fresh"


def test_a_key_reassigned_after_loading_is_left_alone() -> None:
    ctx = _ctx({"name": "my-app"}, {"DATABASE_URL": "new-dsn"}, {"DATABASE_URL": "minted-dsn"})
    _preserve(ctx, _Ssh("DATABASE_URL=stale-dsn\n"))
    assert ctx.secrets["DATABASE_URL"] == "new-dsn"


def test_a_failed_remote_read_aborts_before_anything_is_written() -> None:
    ctx = _ctx({"name": "my-app"}, {"MASTERKEY": "fresh"}, {"MASTERKEY": "fresh"})
    with pytest.raises(DeployError):
        _preserve(ctx, _Ssh("MASTERKEY=first-apply\n", fail=True))


def test_a_local_source_reads_the_env_at_its_own_path() -> None:
    ctx = _ctx({"name": "my-app"}, {"MASTERKEY": "fresh"}, {"MASTERKEY": "fresh"})
    ssh = _Ssh("MASTERKEY=first-apply\n")
    _preserve(ctx, ssh, {"type": "local", "path": "/opt/file-worker"}, SourceType.LOCAL)
    assert ctx.secrets["MASTERKEY"] == "first-apply"
    assert any("/opt/file-worker/.env" in c for c in ssh.calls)


def test_the_template_render_sees_the_deployed_value() -> None:
    """The template path bakes secrets into compose.yaml — the render must get the kept value."""
    spec = {"name": "my-app", "id": "my-app", "source": {"type": "template"},
            "template": "python-api", "domain": "my-app.example.com"}
    ctx = _ctx(spec, {"MASTERKEY": "fresh"}, {"MASTERKEY": "fresh"})
    seen: dict[str, str] = {}

    class _StopRenderError(Exception):
        pass

    def _render(self, spec, secrets=None, dry_run=False):  # noqa: ARG001
        seen.update(secrets or {})
        raise _StopRenderError

    with patch("fabrik.drivers.ssh.ssh", _Ssh("MASTERKEY=first-apply\n")), \
         patch.object(SSHDeployer, "find_existing", return_value={"name": "my-app"}), \
         patch("fabrik.template_renderer.TemplateRenderer.render", _render), \
         pytest.raises(_StopRenderError):
        SSHDeployer()._deploy_inner(ctx)
    assert seen["MASTERKEY"] == "first-apply"


def test_the_deployed_value_is_never_logged(caplog) -> None:
    ctx = _ctx({"name": "my-app"}, {"MASTERKEY": "fresh"}, {"MASTERKEY": "fresh"})
    with caplog.at_level(logging.DEBUG):
        _preserve(ctx, _Ssh("MASTERKEY=first-apply\n"))
    assert "MASTERKEY" in caplog.text
    assert "first-apply" not in caplog.text
    assert "fresh" not in caplog.text


class _FakeManager:
    """Resolves ``A`` from the hub; must invent anything else."""

    def load_all(self, keys: list[str], generate_if_missing: bool = True) -> dict[str, str]:
        out: dict[str, str] = {}
        for key in keys:
            if key == "A":
                out[key] = "from-hub"
            elif generate_if_missing:
                out[key] = f"minted-{key}"
        return out

    def get_missing(self, keys: list[str]) -> list[str]:
        return [k for k in keys if k != "A"]


@pytest.mark.parametrize("secrets_block", [
    {"generate": ["A", "B"], "from_env": ["FROM_ENV_KEY"]},
    {"required": ["A", "B"], "from_env": ["FROM_ENV_KEY"]},
    ["A", "B"],
])
def test_load_secrets_records_only_the_minted_keys(monkeypatch, secrets_block) -> None:
    monkeypatch.setenv("FROM_ENV_KEY", "env-value")
    orch = DeploymentOrchestrator()
    orch.secrets_manager = _FakeManager()
    ctx = _ctx({"id": "my-app", "name": "my-app"}, {}, {})
    orch._load_secrets(ctx, {"id": "my-app", "name": "my-app", "secrets": secrets_block})
    assert ctx.minted_secrets == {"B": "minted-B"}
    assert ctx.secrets["A"] == "from-hub"
