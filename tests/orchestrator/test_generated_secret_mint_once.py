"""Mint-once: a secret the hub INVENTED never overwrites the value the remote ``.env`` holds.

W-023bdd59 — ``SecretsManager`` mints a fresh value for a ``generate``/``required`` key the hub cannot
resolve, and the hub never holds the value it minted on the first apply (it went only into the remote
``/opt/<app>/.env``). ``SSHDeployer._build_env_content`` then layered every ``ctx.secrets`` value over
the remote ``.env``, so each re-apply replaced a stable-forever key (Zitadel's ``ZITADEL_MASTERKEY``)
with a new one. These tests drive the merge through the ``fabrik.drivers.ssh.ssh`` seam and the
orchestrator's secret loading through a fake manager; nothing reaches a host.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

from fabrik.orchestrator import DeploymentOrchestrator
from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.deployer_ssh import SSHDeployer

_EXISTING = {"name": "my-app", "status": "", "path": "/opt/my-app"}


def _ctx(spec: dict) -> DeploymentContext:
    ctx = DeploymentContext(spec_path=Path("test.yaml"))
    ctx.spec = spec
    return ctx


def _parse(env_text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in env_text.splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip().strip("'\"")
    return out


def _build(ctx: DeploymentContext, remote_env: str | None) -> dict[str, str]:
    """Run the deploy-time merge; ``remote_env`` None means a first deploy (no existing app)."""
    if remote_env is None:
        return _parse(SSHDeployer()._build_env_content(ctx, "my-app", existing=None))
    with patch("fabrik.drivers.ssh.ssh", side_effect=["present", remote_env]):
        return _parse(SSHDeployer()._build_env_content(ctx, "my-app", existing=_EXISTING))


def test_reapply_keeps_remote_generated_secret() -> None:
    ctx = _ctx({"name": "my-app", "env": {}})
    ctx.secrets = {"MASTERKEY": "freshly-minted"}
    ctx.minted_secrets = {"MASTERKEY"}
    built = _build(ctx, "MASTERKEY=first-apply-value\n")
    assert built["MASTERKEY"] == "first-apply-value"
    assert ctx.secrets["MASTERKEY"] == "first-apply-value"


def test_first_deploy_writes_minted_secret() -> None:
    ctx = _ctx({"name": "my-app", "env": {}})
    ctx.secrets = {"MASTERKEY": "freshly-minted"}
    ctx.minted_secrets = {"MASTERKEY"}
    assert _build(ctx, None)["MASTERKEY"] == "freshly-minted"


def test_hub_supplied_secret_still_overwrites() -> None:
    ctx = _ctx({"name": "my-app", "env": {}})
    ctx.secrets = {"API_KEY": "rotated-by-operator"}
    ctx.minted_secrets = set()
    assert _build(ctx, "API_KEY=old-value\n")["API_KEY"] == "rotated-by-operator"


def test_empty_remote_value_is_filled() -> None:
    ctx = _ctx({"name": "my-app", "env": {}})
    ctx.secrets = {"MASTERKEY": "freshly-minted"}
    ctx.minted_secrets = {"MASTERKEY"}
    assert _build(ctx, "MASTERKEY=\n")["MASTERKEY"] == "freshly-minted"


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


def test_load_secrets_records_only_minted_keys(monkeypatch) -> None:
    monkeypatch.setenv("FROM_ENV_KEY", "env-value")
    orch = DeploymentOrchestrator()
    orch.secrets_manager = _FakeManager()
    for block in ("generate", "required"):
        ctx = _ctx({"id": "my-app", "name": "my-app"})
        spec = {"id": "my-app", "name": "my-app", "secrets": {block: ["A", "B"], "from_env": ["FROM_ENV_KEY"]}}
        orch._load_secrets(ctx, spec)
        assert ctx.minted_secrets == {"B"}, block
        assert ctx.secrets["A"] == "from-hub"
        assert ctx.secrets["B"] == "minted-B"


def test_preserved_value_is_never_logged(caplog) -> None:
    ctx = _ctx({"name": "my-app", "env": {}})
    ctx.secrets = {"MASTERKEY": "freshly-minted"}
    ctx.minted_secrets = {"MASTERKEY"}
    with caplog.at_level(logging.DEBUG):
        _build(ctx, "MASTERKEY=first-apply-value\n")
    text = caplog.text
    assert "MASTERKEY" in text
    assert "first-apply-value" not in text
    assert "freshly-minted" not in text
